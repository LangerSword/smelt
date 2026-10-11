package replay

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/x/exp/teatest"
)

// Fake-smelt driven live tests. Deterministic, no API calls.
// See testdata/fake-smelt.sh for the scripted event stream.

func fakeSmeltPath(t *testing.T) string {
	t.Helper()
	abs, err := filepath.Abs(filepath.Join("..", "..", "testdata", "fake-smelt.sh"))
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(abs, 0o755); err != nil { // defensive; git records the mode
		t.Fatal(err)
	}
	return abs
}

func startFakeLive(t *testing.T, env map[string]string) (*Model, *LiveRun) {
	t.Helper()
	dir := t.TempDir()
	runsDir := filepath.Join(dir, "runs")
	t.Setenv("FAKE_RUNS_DIR", runsDir)
	for k, v := range env {
		t.Setenv(k, v)
	}
	live, err := StartLive(fakeSmeltPath(t), "fake.py:fn", "fake", "fake-model", runsDir)
	if err != nil {
		t.Fatalf("StartLive: %v", err)
	}
	return NewLive(&RunSummary{Dir: runsDir, Status: "in_progress"}, live), live
}

func TestResolveSmeltErrorsOnMissingExplicitPath(t *testing.T) {
	if _, err := ResolveSmelt("/nonexistent/definitely-not-smelt"); err == nil {
		t.Fatal("expected an error for a missing explicit path")
	}
	if p, err := ResolveSmelt(fakeSmeltPath(t)); err != nil || p == "" {
		t.Fatalf("explicit existing path should resolve: %v", err)
	}
}

func TestLiveFakeRunCompletes(t *testing.T) {
	m, _ := startFakeLive(t, map[string]string{"FAKE_SLEEP": "0"})
	tm := teatest.NewTestModel(t, m, teatest.WithInitialTermSize(100, 30))
	// the accepted run auto-opens the Result screen — its frame proves
	// acceptance + done + auto-open in one condition (waiting for "INGOT"
	// first would consume the same output chunk and miss this one)
	teatest.WaitFor(t, tm.Output(),
		func(b []byte) bool { return bytes.Contains(b, []byte("[1 summary]")) },
		teatest.WithDuration(8*time.Second))
	tm.Send(keyRunes('q'))
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

	fin := tm.FinalModel(t).(*Model)
	if !fin.ResultOpen() {
		t.Fatal("accepted live run must auto-open the Result screen")
	}
	if !fin.Done || fin.ExitCode != 0 {
		t.Fatalf("done=%v exit=%d", fin.Done, fin.ExitCode)
	}
	if fin.Sum.NCases != 42 {
		t.Fatalf("oracle cases = %d, want 42", fin.Sum.NCases)
	}
	if !fin.Sum.HasSpeedup || !almost(fin.Sum.Speedup, 2.5) || !almost(fin.Sum.SpeedupLB, 2.2) {
		t.Fatalf("speedup=%v lb=%v", fin.Sum.Speedup, fin.Sum.SpeedupLB)
	}
	if fin.Sum.Status != "accepted" {
		t.Fatalf("status=%q", fin.Sum.Status)
	}
}

func TestLiveBadJSONLineSkippedAndLogged(t *testing.T) {
	m, _ := startFakeLive(t, map[string]string{"FAKE_SLEEP": "0", "FAKE_BADJSON": "1"})
	tm := teatest.NewTestModel(t, m, teatest.WithInitialTermSize(100, 30))
	// the run ends accepted → the Result screen auto-opens on top of the run
	// screen; the log (with its skipped-line note) is visible again after esc
	teatest.WaitFor(t, tm.Output(),
		func(b []byte) bool { return bytes.Contains(b, []byte("[1 summary]")) },
		teatest.WithDuration(8*time.Second))
	tm.Send(tea.KeyMsg{Type: tea.KeyEscape})
	teatest.WaitFor(t, tm.Output(),
		func(b []byte) bool { return bytes.Contains(b, []byte("skipped")) },
		teatest.WithDuration(8*time.Second))
	tm.Send(keyRunes('q'))
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

	fin := tm.FinalModel(t).(*Model)
	if fin.SkippedLines != 1 {
		t.Fatalf("skipped = %d, want 1", fin.SkippedLines)
	}
	joined := ""
	for _, l := range fin.LogLines {
		joined += l + "\n"
	}
	if !bytes.Contains([]byte(joined), []byte("unparsed line (skipped)")) {
		t.Fatalf("log missing the skipped-line note:\n%s", joined)
	}
}

func TestLiveSubprocessCrashReported(t *testing.T) {
	m, _ := startFakeLive(t, map[string]string{"FAKE_NOEVENTS": "1", "FAKE_EXIT": "1"})
	tm := teatest.NewTestModel(t, m, teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(),
		func(b []byte) bool { return bytes.Contains(b, []byte("exited with code 1")) },
		teatest.WithDuration(8*time.Second))
	tm.Send(keyRunes('q'))
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

	fin := tm.FinalModel(t).(*Model)
	if !fin.Done || fin.ExitCode != 1 {
		t.Fatalf("done=%v exit=%d", fin.Done, fin.ExitCode)
	}
	if fin.CrashNote == "" {
		t.Fatal("crash note missing")
	}
}

func TestLiveKillMidRunLeavesCleanState(t *testing.T) {
	m, live := startFakeLive(t, map[string]string{"FAKE_SLEEP": "3"})
	tm := teatest.NewTestModel(t, m, teatest.WithInitialTermSize(100, 30))
	// Wait until the run is mid-flight (capture_done appears after ~6s).
	teatest.WaitFor(t, tm.Output(),
		func(b []byte) bool { return bytes.Contains(b, []byte("oracle frozen")) },
		teatest.WithDuration(15*time.Second))
	tm.Send(tea.KeyMsg{Type: tea.KeyCtrlC})
	tm.WaitFinished(t, teatest.WithFinalTimeout(5*time.Second))

	fin := tm.FinalModel(t).(*Model)
	if !fin.KilledByUser {
		t.Fatal("KilledByUser not set")
	}
	if fin.Done {
		t.Fatal("killed run must not be marked done")
	}
	if live.Cmd.ProcessState == nil {
		t.Fatal("child process state missing (not waited)")
	}
	if live.Cmd.ProcessState.Success() {
		t.Fatal("child should not have exited successfully after kill")
	}
}

// The live view must also fit an 80-column terminal (with a nil Live guard).
func TestLiveViewFits80Columns(t *testing.T) {
	sum := load(t, "accepted-gemini")
	m := &Model{Sum: sum, Mode: ModeLive, Width: 80, Height: 24, ExitCode: -1}
	lines := splitView(m)
	for _, ln := range lines {
		if len([]rune(ln)) > 80 {
			t.Fatalf("line over 80 cols: %q", ln)
		}
	}
}

func splitView(m *Model) []string {
	return strings.Split(m.View(), "\n")
}

// Regression: StartLive must pass --runs-dir so the subprocess writes to the
// same directory the viewer tails (it silently wrote to the cwd default before).
func TestStartLivePassesRunsDir(t *testing.T) {
	bin := fakeSmeltPath(t)
	l, err := StartLive(bin, "fake/demo/fake.py:fake_fn", "fake", "", "custom-runs")
	if err != nil {
		t.Fatal(err)
	}
	defer l.Kill()
	joined := strings.Join(l.Cmd.Args, " ")
	if !strings.Contains(joined, "--runs-dir custom-runs") {
		t.Fatalf("StartLive args missing --runs-dir: %s", joined)
	}
}
