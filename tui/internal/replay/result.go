package replay

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// ResultData is the Result screen's assembly of ONE run, read from
// runs/<id>/ artifacts only (state.json, events.jsonl, attempts/*, and the
// frozen source when it is still readable). Loading never fails: every gap
// becomes an explicit message so the screen degrades instead of crashing.
type ResultData struct {
	Dir         string
	RunID       string
	Status      string
	Reason      string
	CreatedAt   string
	Version     string
	TargetPath  string
	Qualname    string
	SourceSHA   string
	Provider    string
	Model       string
	NCases      int
	OracleSHA   string
	MaxAttempts int

	Attempts []ResultAttempt

	Lib        string
	LibAttempt int
	LibErr     string
	LibNote    string

	Python        string
	PythonErr     string
	PythonChanged bool

	Refusal     string
	RefusalHint string

	Diff     []string
	DiffNote string

	LastBench string
}

// ResultAttempt is one row of the attempts strip (the feedback loop made
// visible: compile error → mismatch → no gain → accepted).
type ResultAttempt struct {
	N       int
	Source  string
	Build   string
	Verify  string
	Bench   string
	Outcome string
	Sample  *MismatchSample
}

// MismatchSample is the first failing oracle case recorded by verify.json
// (input, expected, got — pre-rendered for the strip).
type MismatchSample struct {
	CaseID string
	Why    string
	Args   []string
	Want   string
	Got    string
}

var attemptDirRe = regexp.MustCompile(`^it([0-9]+)$`)

// LoadResult assembles the Result screen's data. It never returns an error:
// missing artifacts land in the matching field (LibErr, PythonErr, DiffNote).
func LoadResult(dir string) *ResultData {
	r := &ResultData{Dir: dir}
	st := readJSONMap(filepath.Join(dir, "state.json"))
	if st != nil {
		r.RunID = asStr(st["run_id"])
		r.Status = asStr(st["status"])
		r.Reason = asStr(st["stop_reason"])
		r.CreatedAt = asStr(st["created_at"])
		r.Version = asStr(st["smelt_version"])
		if tgt, ok := st["target"].(map[string]any); ok {
			r.TargetPath = asStr(tgt["path"])
			r.Qualname = asStr(tgt["qualname"])
			r.SourceSHA = asStr(tgt["source_sha256"])
		}
		if cfg, ok := st["config"].(map[string]any); ok {
			r.Provider = asStr(cfg["provider"])
			r.Model = asStr(cfg["model"])
			r.MaxAttempts = int(asFloat(cfg["max_attempts"]))
		}
		if orc, ok := st["oracle"].(map[string]any); ok {
			r.NCases = int(asFloat(orc["n_cases"]))
			r.OracleSHA = asStr(orc["sha256"])
		}
		if atts, ok := st["attempts"].([]any); ok {
			for i, raw := range atts {
				am, _ := raw.(map[string]any)
				if am == nil {
					continue
				}
				n := int(asFloat(am["attempt"]))
				if n == 0 {
					n = i + 1
				}
				r.Attempts = append(r.Attempts, ResultAttempt{
					N:       n,
					Source:  asStr(am["source"]),
					Build:   asStr(am["build"]),
					Verify:  asStr(am["verify"]),
					Bench:   asStr(am["bench"]),
					Outcome: asStr(am["outcome"]),
				})
			}
		}
	}
	if r.RunID == "" {
		r.RunID = filepath.Base(strings.TrimRight(dir, "/"))
	}
	// One events read powers the fallbacks: status/cases when state.json is
	// silent (killed or minimal runs), per-attempt outcomes, the halt message.
	sum, _ := LoadRun(dir)
	if sum != nil {
		if r.Status == "" {
			r.Status = sum.Status
		}
		if r.NCases == 0 {
			r.NCases = sum.NCases
		}
	}
	if len(r.Attempts) == 0 && sum != nil {
		r.Attempts = attemptsFromSummary(sum)
	}
	for i := range r.Attempts {
		r.Attempts[i].Sample = loadMismatchSample(attemptPath(dir, r.Attempts[i].N, "verify.json"))
	}
	if n := len(r.Attempts); n > 0 {
		if b := r.Attempts[n-1].Bench; b != "" {
			r.LastBench = b
		}
	}

	// Final candidate lib.rs: the last attempt that actually stores one.
	lastN := lastAttemptNumber(dir, r.Attempts)
	for n := lastN; n >= 1; n-- {
		if b, err := os.ReadFile(attemptPath(dir, n, "lib.rs")); err == nil {
			r.Lib = string(b)
			r.LibAttempt = n
			if n < lastN {
				r.LibNote = fmt.Sprintf("last attempt it%d has no lib.rs — showing it%d", lastN, n)
			}
			break
		}
	}
	if r.Lib == "" {
		switch {
		case r.Status == "refused":
			r.LibErr = "not generated — the run was refused before generation"
		case r.Status == "error":
			r.LibErr = "not generated — the run stopped with an error"
		case lastN == 0:
			r.LibErr = "no attempt artifacts found in this run dir"
		default:
			r.LibErr = fmt.Sprintf("attempts/it%d/lib.rs is missing from this run dir", lastN)
		}
	}

	// Frozen Python source. state.json records the path; a run-relative path
	// (the fixture convention for hermetic tests) resolves against the run dir.
	if r.TargetPath != "" {
		p := r.TargetPath
		if !filepath.IsAbs(p) {
			p = filepath.Join(dir, p)
		}
		if b, err := os.ReadFile(p); err == nil {
			r.Python = string(b)
			if r.SourceSHA != "" {
				h := sha256.Sum256(b)
				if hex.EncodeToString(h[:]) != r.SourceSHA {
					r.PythonChanged = true
				}
			}
		} else {
			r.PythonErr = "cannot read " + p
		}
	} else {
		r.PythonErr = "no target path recorded in state.json"
	}

	// Refusal / error reason, split from the refactor hint when the halt
	// message carries one ("… — refactor hint: …" / "; refactor hint: …").
	var haltMsg string
	if sum != nil {
		for _, ev := range sum.Events {
			if ev.Event == "halt" {
				haltMsg = asStr(ev.Raw["message"])
			}
		}
	}
	if haltMsg == "" && r.Reason != "" {
		haltMsg = r.Reason
		if i := strings.Index(haltMsg, ": "); i > 0 && isKindLike(haltMsg[:i]) {
			haltMsg = haltMsg[i+2:]
		}
	}
	if i := strings.LastIndex(haltMsg, "refactor hint: "); i >= 0 {
		r.RefusalHint = strings.TrimSpace(haltMsg[i+len("refactor hint: "):])
		haltMsg = strings.TrimSpace(strings.TrimRight(strings.TrimSpace(haltMsg[:i]), ";—"))
	}
	r.Refusal = haltMsg

	// The view-only diff, composed like `smelt apply` prints it (apply.py).
	switch {
	case r.Status == "accepted" && r.Lib != "":
		r.Diff = composeApplyView(r)
	case r.Status == "accepted":
		r.DiffNote = "smelt apply: candidate lib.rs not found in the run dir"
	case r.Status == "":
		r.DiffNote = "smelt apply: no state.json — cannot determine the run status"
	default:
		r.DiffNote = fmt.Sprintf("smelt apply: run %s is '%s' — nothing to apply (only accepted runs carry a verified candidate)", r.RunID, r.Status)
	}
	return r
}

// composeApplyView mirrors the text `smelt apply <run-dir>` prints (view
// only): the new-file diff for the crate, the build command, the safe shim,
// and — furnace's addition — an explicit revert note.
func composeApplyView(r *ResultData) []string {
	fn := r.Qualname
	if fn == "" {
		fn = "fn"
	}
	out := []string{
		fmt.Sprintf("# smelt apply — %s · VIEW ONLY (nothing is written)", r.RunID),
		fmt.Sprintf("# target : %s:%s", r.TargetPath, fn),
		fmt.Sprintf("# status : accepted · %s", r.LastBench),
		"",
		"--- /dev/null",
		fmt.Sprintf("+++ rust/%s/src/lib.rs", fn),
	}
	for _, ln := range strings.Split(strings.TrimRight(strings.ReplaceAll(r.Lib, "\r\n", "\n"), "\n"), "\n") {
		out = append(out, "+"+ln)
	}
	out = append(out,
		"",
		"## build (manual, in a scratch dir)",
		fmt.Sprintf("#   cd rust/%s && maturin develop --release", fn),
		"",
		"## safe shim — fall back to the original if the extension is unavailable",
		"```python",
		"try:",
		fmt.Sprintf("    from rust.%s import %s as _fast  # built by smelt, oracle-verified", fn, fn),
		fmt.Sprintf("    %s = _fast", fn),
		"except Exception:  # extension missing — keep the Python original",
		"    pass",
		"```",
		"",
		"## revert",
		"#   view only — nothing was written into your repo. After applying the change",
		fmt.Sprintf("#   by hand: delete rust/%s/ and remove the shim block; the Python original is untouched.", fn),
	)
	return out
}

// attemptPath is runs/<dir>/attempts/it<N>/<name>.
func attemptPath(dir string, n int, name string) string {
	return filepath.Join(dir, "attempts", fmt.Sprintf("it%d", n), name)
}

// attemptDirNumbers lists the attempts/it<N> directories, numerically sorted.
func attemptDirNumbers(dir string) []int {
	entries, err := os.ReadDir(filepath.Join(dir, "attempts"))
	if err != nil {
		return nil
	}
	var out []int
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		if m := attemptDirRe.FindStringSubmatch(e.Name()); m != nil {
			if n, err := strconv.Atoi(m[1]); err == nil {
				out = append(out, n)
			}
		}
	}
	sort.Ints(out)
	return out
}

// lastAttemptNumber is the highest attempt number known from either the
// attempt directories or the state.json records.
func lastAttemptNumber(dir string, atts []ResultAttempt) int {
	max := 0
	for _, n := range attemptDirNumbers(dir) {
		if n > max {
			max = n
		}
	}
	for _, a := range atts {
		if a.N > max {
			max = a.N
		}
	}
	return max
}

// attemptsFromSummary rebuilds per-attempt outcomes from the event stream,
// used when state.json carries no attempts[] array.
func attemptsFromSummary(sum *RunSummary) []ResultAttempt {
	var out []ResultAttempt
	idx := map[int]int{}
	cur := -1
	ensure := func(n int) int {
		if i, ok := idx[n]; ok {
			cur = i
			return i
		}
		out = append(out, ResultAttempt{N: n})
		idx[n] = len(out) - 1
		cur = len(out) - 1
		return cur
	}
	for _, ev := range sum.Events {
		switch ev.Event {
		case "attempt_start":
			ensure(int(asFloat(ev.Raw["attempt"])))
		case "safety_violation":
			i := ensure(int(asFloat(ev.Raw["attempt"])))
			out[i].Outcome = "safety_violation: safety scan failed"
		case "build_error":
			i := ensure(int(asFloat(ev.Raw["attempt"])))
			out[i].Outcome = "build_error[" + asStr(ev.Raw["subkind"]) + "]: cargo build failed"
		case "verify_mismatch":
			i := ensure(int(asFloat(ev.Raw["attempt"])))
			out[i].Outcome = fmt.Sprintf("verify_mismatch: %d case(s) differ", int(asFloat(ev.Raw["n_bad"])))
		case "reject_no_meaningful_gain":
			if cur >= 0 {
				out[cur].Outcome = fmt.Sprintf("reject_no_meaningful_gain: ratio %.2fx", asFloat(ev.Raw["ratio"]))
			}
		case "accept":
			if cur >= 0 {
				out[cur].Outcome = "ACCEPTED"
				out[cur].Bench = fmt.Sprintf("%.2fx (lb %.2fx)", asFloat(ev.Raw["ratio"]), asFloat(ev.Raw["ratio_ci_lo"]))
			}
		}
	}
	return out
}

// loadMismatchSample reads attempts/it<N>/verify.json and pre-renders the
// first failing case: input, expected, got.
func loadMismatchSample(path string) *MismatchSample {
	m := readJSONMap(path)
	if m == nil {
		return nil
	}
	sample, _ := m["sample"].([]any)
	if len(sample) == 0 {
		return nil
	}
	sm, _ := sample[0].(map[string]any)
	if sm == nil {
		return nil
	}
	out := &MismatchSample{CaseID: asStr(sm["case_id"]), Why: asStr(sm["why"])}
	if args, ok := sm["args"].([]any); ok {
		for _, a := range args {
			out.Args = append(out.Args, renderJSONValue(a))
		}
	}
	out.Want = renderObserved(sm["expected"], sm["expected_err"])
	out.Got = renderObserved(sm["got"], sm["got_err"])
	return out
}

// renderObserved renders an expected/got slot: the recorded exception when
// one was raised, otherwise "type value".
func renderObserved(v any, errv any) string {
	if s := asStr(errv); s != "" {
		return s
	}
	if m, ok := v.(map[string]any); ok {
		return fmt.Sprintf("%s %s", asStr(m["t"]), renderJSONValue(m["v"]))
	}
	return ""
}

// renderJSONValue renders a decoded JSON value with big integers intact
// (json.Number survives the decode on purpose).
func renderJSONValue(v any) string {
	switch t := v.(type) {
	case nil:
		return "null"
	case string:
		return strconv.Quote(t)
	case json.Number:
		return t.String()
	case bool:
		return strconv.FormatBool(t)
	case []any:
		parts := make([]string, len(t))
		for i := range t {
			parts[i] = renderJSONValue(t[i])
		}
		return "[" + strings.Join(parts, " ") + "]"
	}
	b, err := json.Marshal(v)
	if err != nil {
		return fmt.Sprintf("%v", v)
	}
	return string(b)
}

// readJSONMap decodes a JSON object with UseNumber so large integers survive.
// Any failure returns nil (callers treat that as "artifact missing").
func readJSONMap(path string) map[string]any {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.UseNumber()
	var m map[string]any
	if dec.Decode(&m) != nil {
		return nil
	}
	return m
}

// isKindLike reports whether s looks like a failure kind token
// (lowercase letters, digits, underscores — e.g. "refused_impure").
func isKindLike(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if !(r >= 'a' && r <= 'z' || r >= '0' && r <= '9' || r == '_') {
			return false
		}
	}
	return true
}
