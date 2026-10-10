// Package replay implements Furnace's read-only run viewer: it parses a
// smelt run directory (events.jsonl + state.json) and renders the loop,
// results, log and verdict in a Bubble Tea TUI.
//
// Furnace is a front end. The Python core is the source of truth; this
// package never executes generated code and never reads secrets.
package replay

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

// Event is one line of events.jsonl (docs/events.md).
type Event struct {
	Ts     float64
	Schema string
	Event  string
	Raw    map[string]any
}

// RunSummary is everything the viewer needs about a finished (or killed) run.
type RunSummary struct {
	Dir        string
	RunID      string
	Target     string
	Provider   string
	Model      string
	Status     string // accepted | rejected | refused | error | in_progress
	Events     []Event
	BadLines   int
	NCases     int
	OracleSHA  string
	Attempts   int
	Speedup    float64
	SpeedupLB  float64
	HasSpeedup bool
	HasLB      bool
	Reason     string
	Log        []string
}

var benchRe = regexp.MustCompile(`([0-9]+(?:\.[0-9]+)?)x \(lb ([0-9]+(?:\.[0-9]+)?)x\)`)

func asStr(v any) string {
	s, _ := v.(string)
	return s
}

func asFloat(v any) float64 {
	switch t := v.(type) {
	case float64:
		return t
	case string:
		f, _ := strconv.ParseFloat(t, 64)
		return f
	}
	return 0
}

// LoadRun reads events.jsonl (skipping, and counting, malformed lines) and
// augments the summary from state.json when present.
func LoadRun(dir string) (*RunSummary, error) {
	evPath := filepath.Join(dir, "events.jsonl")
	f, err := os.Open(evPath)
	if err != nil {
		return nil, fmt.Errorf("cannot open %s: %w", evPath, err)
	}
	defer f.Close()

	s := &RunSummary{Dir: dir, Status: ""}
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var raw map[string]any
		if err := json.Unmarshal([]byte(line), &raw); err != nil {
			s.BadLines++
			continue
		}
		ev := Event{
			Ts:     asFloat(raw["ts"]),
			Schema: asStr(raw["schema_version"]),
			Event:  asStr(raw["event"]),
			Raw:    raw,
		}
		s.Events = append(s.Events, ev)
		s.consume(ev)
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	s.loadState(filepath.Join(dir, "state.json"))
	if s.Model == "-" { // orchestrator emits "-" when no model is involved
		s.Model = ""
	}
	if s.RunID == "" {
		s.RunID = filepath.Base(strings.TrimRight(dir, "/"))
	}
	if s.Attempts == 0 {
		for _, ev := range s.Events {
			if ev.Event == "attempt_start" {
				s.Attempts++
			}
		}
	}
	if s.Status == "" {
		s.Status = deriveStatus(s)
	}
	s.Log = s.buildLog()
	return s, nil
}

func (s *RunSummary) consume(ev Event) {
	switch ev.Event {
	case "run_start":
		if t := asStr(ev.Raw["target"]); t != "" {
			s.Target = t
		}
		if p := asStr(ev.Raw["provider"]); p != "" {
			s.Provider = p
		}
		if m := asStr(ev.Raw["model"]); m != "" {
			s.Model = m
		}
	case "capture_done":
		s.NCases = int(asFloat(ev.Raw["n_cases"]))
		s.OracleSHA = asStr(ev.Raw["sha256"])
	case "accept":
		s.Speedup = asFloat(ev.Raw["ratio"])
		s.SpeedupLB = asFloat(ev.Raw["ratio_ci_lo"])
		s.HasSpeedup = true
		s.HasLB = s.SpeedupLB > 0
	case "reject_no_meaningful_gain":
		if r := asFloat(ev.Raw["ratio"]); r > 0 && !s.HasSpeedup {
			s.Speedup = r
			s.HasSpeedup = true
		}
	case "run_end":
		if st := asStr(ev.Raw["status"]); st != "" {
			s.Status = st
		}
		if r := asStr(ev.Raw["reason"]); r != "" {
			s.Reason = r
		}
	}
}

func (s *RunSummary) loadState(path string) {
	b, err := os.ReadFile(path)
	if err != nil {
		return
	}
	var st map[string]any
	if json.Unmarshal(b, &st) != nil {
		return
	}
	if v := asStr(st["run_id"]); v != "" {
		s.RunID = v
	}
	if v := asStr(st["status"]); v != "" {
		s.Status = v
	}
	if v := asStr(st["stop_reason"]); v != "" {
		s.Reason = v
	}
	if cfg, ok := st["config"].(map[string]any); ok {
		if v := asStr(cfg["provider"]); v != "" {
			s.Provider = v
		}
		if v := asStr(cfg["model"]); v != "" {
			s.Model = v
		}
	}
	if tgt, ok := st["target"].(map[string]any); ok {
		if v := asStr(tgt["path"]); v != "" {
			s.Target = v
		}
		if q := asStr(tgt["qualname"]); q != "" && !strings.HasSuffix(s.Target, ":"+q) {
			s.Target = s.Target + ":" + q
		}
	}
	atts, _ := st["attempts"].([]any)
	if len(atts) > 0 {
		s.Attempts = len(atts)
		// The final attempt record carries the decisive benchmark string,
		// e.g. "4.14x (lb 4.00x)" — authoritative for both accept and reject.
		if last, ok := atts[len(atts)-1].(map[string]any); ok {
			if bench := asStr(last["bench"]); bench != "" {
				if m := benchRe.FindStringSubmatch(bench); m != nil {
					s.Speedup = asFloat(m[1])
					s.SpeedupLB = asFloat(m[2])
					s.HasSpeedup = true
					s.HasLB = true
				}
			}
		}
	}
}

func deriveStatus(s *RunSummary) string {
	var lastHalt string
	for _, ev := range s.Events {
		if ev.Event == "halt" {
			lastHalt = asStr(ev.Raw["kind"])
		}
	}
	switch {
	case strings.HasPrefix(lastHalt, "refused"):
		return "refused"
	case lastHalt != "":
		return "error"
	default:
		return "in_progress"
	}
}

func (s *RunSummary) buildLog() []string {
	var out []string
	for _, ev := range s.Events {
		switch ev.Event {
		case "run_start":
			out = append(out, "run start · provider="+s.Provider+" model="+DisplayModel(s.Provider, s.Model))
		case "capture_done":
			out = append(out, fmt.Sprintf("oracle frozen · %d cases · sha %s", s.NCases, s.OracleSHA))
		case "attempt_start":
			out = append(out, fmt.Sprintf("attempt %d · generate", int(asFloat(ev.Raw["attempt"]))))
		case "resume":
			out = append(out, fmt.Sprintf("resume · from attempt %d", int(asFloat(ev.Raw["from_attempt"]))))
		case "safety_violation":
			out = append(out, fmt.Sprintf("attempt %d · safety violation", int(asFloat(ev.Raw["attempt"]))))
		case "build_error":
			out = append(out, fmt.Sprintf("attempt %d · build error · %s", int(asFloat(ev.Raw["attempt"])), asStr(ev.Raw["subkind"])))
		case "verify_mismatch":
			out = append(out, fmt.Sprintf("attempt %d · verify mismatch · %d case(s) differ", int(asFloat(ev.Raw["attempt"])), int(asFloat(ev.Raw["n_bad"]))))
		case "accept":
			out = append(out, fmt.Sprintf("accept · %.2fx (lower bound %.2fx)", asFloat(ev.Raw["ratio"]), asFloat(ev.Raw["ratio_ci_lo"])))
		case "reject_no_meaningful_gain":
			out = append(out, fmt.Sprintf("reject · %.2fx median (below 1.5x threshold)", asFloat(ev.Raw["ratio"])))
		case "halt":
			out = append(out, "halt · "+asStr(ev.Raw["message"]))
		case "run_end":
			out = append(out, "end · "+asStr(ev.Raw["status"]))
		}
	}
	if s.Reason != "" {
		out = append(out, "reason · "+s.Reason)
	}
	return out
}

// FlowNodes is the rendered loop, left to right (docs/events.md).
var FlowNodes = []string{"select", "oracle", "generate", "build", "verify", "bench", "verdict"}

// FlowNode maps an event type to the flow node it advances ("" = none).
func FlowNode(ev string) string {
	switch ev {
	case "purity_ok":
		return "select"
	case "capture_done":
		return "oracle"
	case "attempt_start", "resume", "safety_violation":
		return "generate"
	case "build_error":
		return "build"
	case "verify_mismatch":
		return "verify"
	case "accept", "reject_no_meaningful_gain":
		return "verdict"
	}
	return ""
}

// FlowReached reports which flow nodes the run reached. Later stages imply
// earlier ones (bench stages silently between verify and accept/reject).
func (s *RunSummary) FlowReached() map[string]bool {
	r := map[string]bool{}
	max := -1
	for _, ev := range s.Events {
		if ev.Event == "halt" && strings.HasPrefix(asStr(ev.Raw["kind"]), "refused") {
			// Refusal happens during the purity probe (select stage) —
			// there is no purity_ok event for it.
			r["select"] = true
			if max < 0 {
				max = 0
			}
			continue
		}
		if n := FlowNode(ev.Event); n != "" {
			r[n] = true
			for i, fn := range FlowNodes {
				if fn == n && i > max {
					max = i
				}
			}
		}
	}
	for i := 0; i <= max; i++ {
		r[FlowNodes[i]] = true
	}
	return r
}

// Verdict maps run status to the furnace verdict word.
func Verdict(status string) (string, string) {
	switch status {
	case "accepted":
		return "INGOT", "accepted — verified rewrite, speedup above the threshold"
	case "rejected":
		return "SLAG", "rejected — correct but no meaningful gain (or budget exhausted)"
	case "refused":
		return "ASH", "refused — impure target (a correct outcome)"
	case "error":
		return "ASH", "stopped with an error — see the log"
	case "in_progress":
		return "COLD", "run did not finish — stream has no run_end"
	default:
		return strings.ToUpper(status), status
	}
}

// DisplayModel renders the model label, honestly distinguishing the
// file-provider fixture (no model involved).
func DisplayModel(provider, model string) string {
	if model != "" {
		return model
	}
	if provider == "file" || provider == "fake" {
		return "— (no model: " + provider + " fixture)"
	}
	return "—"
}
