package replay

import (
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"time"
)

// LiveRun spawns `smelt run <target> --provider <p> --json` as a subprocess
// and tails the new run's events.jsonl. Furnace is a front end: it never
// runs generated code itself and never reads secrets — the smelt CLI does
// its normal job, in its own process.
type LiveRun struct {
	Cmd       *exec.Cmd
	RunsDir   string
	RunDir    string
	StartTime time.Time

	evFile    *os.File
	remainder string
	seenDirs  map[string]bool
	Stdout    bytes.Buffer
	Stderr    bytes.Buffer
	doneCh    chan error
	done      bool
	waitErr   error
}

// ResolveSmelt finds the smelt binary: explicit path first, then PATH.
func ResolveSmelt(explicit string) (string, error) {
	if explicit != "" {
		if st, err := os.Stat(explicit); err != nil || st.IsDir() {
			return "", &os.PathError{Op: "smelt", Path: explicit, Err: os.ErrNotExist}
		}
		return explicit, nil
	}
	return exec.LookPath("smelt")
}

// StartLive starts the subprocess and snapshots the runs dir so the new
// run directory can be discovered deterministically.
func StartLive(smeltBin, target, provider, model, runsDir string) (*LiveRun, error) {
	l := &LiveRun{RunsDir: runsDir, StartTime: time.Now(), seenDirs: map[string]bool{}}
	if entries, err := os.ReadDir(runsDir); err == nil {
		for _, e := range entries {
			if e.IsDir() {
				l.seenDirs[e.Name()] = true
			}
		}
	}
	args := []string{"run", target, "--provider", provider, "--json"}
	if model != "" {
		args = append(args, "--model", model)
	}
	if runsDir != "" {
		// Keep the subprocess and the viewer pointed at the same directory
		// (regression: without this, smelt wrote to its cwd-relative default
		// and the viewer tailed an empty directory).
		args = append(args, "--runs-dir", runsDir)
	}
	cmd := exec.Command(smeltBin, args...)
	cmd.Stdout = &l.Stdout
	cmd.Stderr = &l.Stderr
	// Own process group: killing the run also stops its children (e.g. a
	// cargo build), so no orphan work is left behind.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	l.Cmd = cmd
	l.doneCh = make(chan error, 1)
	go func() { l.doneCh <- cmd.Wait() }()
	return l, nil
}

// Poll returns any newly written events (bad JSON lines are skipped and
// returned separately), plus completion state and exit code.
func (l *LiveRun) Poll() (events []Event, bad []string, done bool, exit int) {
	l.discover()
	if l.evFile != nil {
		chunk := make([]byte, 64*1024)
		for {
			n, err := l.evFile.Read(chunk)
			if n > 0 {
				data := l.remainder + string(chunk[:n])
				lines := strings.Split(data, "\n")
				l.remainder = lines[len(lines)-1]
				for _, line := range lines[:len(lines)-1] {
					line = strings.TrimSpace(line)
					if line == "" {
						continue
					}
					var raw map[string]any
					if json.Unmarshal([]byte(line), &raw) != nil {
						bad = append(bad, truncateStr(line, 60))
						continue
					}
					events = append(events, Event{
						Ts:     asFloat(raw["ts"]),
						Schema: asStr(raw["schema_version"]),
						Event:  asStr(raw["event"]),
						Raw:    raw,
					})
				}
			}
			if err != nil { // EOF or a real error — stop reading this tick
				break
			}
		}
	}
	select {
	case err := <-l.doneCh:
		l.done = true
		l.waitErr = err
	default:
	}
	return events, bad, l.done, l.exitCode()
}

// ExitCode returns the subprocess exit code (-1 while running or if killed).
func (l *LiveRun) ExitCode() int { return l.exitCode() }

func (l *LiveRun) exitCode() int {
	if l.Cmd == nil || l.Cmd.ProcessState == nil {
		return -1
	}
	return l.Cmd.ProcessState.ExitCode()
}

// Done reports whether the subprocess has exited.
func (l *LiveRun) Done() bool { return l.done }

func (l *LiveRun) discover() {
	if l.evFile != nil {
		return
	}
	entries, err := os.ReadDir(l.RunsDir)
	if err != nil {
		return
	}
	var candidates []string
	for _, e := range entries {
		if !e.IsDir() || l.seenDirs[e.Name()] {
			continue
		}
		candidates = append(candidates, e.Name())
	}
	if len(candidates) == 0 {
		return
	}
	sort.Strings(candidates)
	dir := filepath.Join(l.RunsDir, candidates[len(candidates)-1])
	f, err := os.Open(filepath.Join(dir, "events.jsonl"))
	if err != nil {
		return
	}
	l.RunDir = dir
	l.evFile = f
}

// Kill stops the subprocess and its process group (used when the user
// quits mid-run), so no orphan cargo/worker processes remain.
func (l *LiveRun) Kill() {
	if l.Cmd == nil || l.Cmd.Process == nil || l.done {
		return
	}
	pid := l.Cmd.Process.Pid
	_ = syscall.Kill(-pid, syscall.SIGKILL) // negative pid = process group
	_ = l.Cmd.Process.Kill()
}

// StderrTail returns the last n non-empty lines of the subprocess stderr.
func (l *LiveRun) StderrTail(n int) []string {
	var lines []string
	for _, ln := range strings.Split(l.Stderr.String(), "\n") {
		ln = strings.TrimSpace(ln)
		if ln != "" {
			lines = append(lines, ln)
		}
	}
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return lines
}

func truncateStr(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}
