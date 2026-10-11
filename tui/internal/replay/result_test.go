package replay

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Result screen unit tests. Fixtures are real run slices — provenance in
// testdata/runs/README.md.

func loadResult(t *testing.T, name string) *ResultData {
	t.Helper()
	return LoadResult(fixturesDir + "/" + name)
}

func TestResultAccepted(t *testing.T) {
	d := loadResult(t, "accepted-gemini")
	if d.Status != "accepted" {
		t.Fatalf("status = %q", d.Status)
	}
	if d.LibAttempt != 1 || !strings.Contains(d.Lib, "fn rle_encode") {
		t.Fatalf("lib attempt=%d len=%d", d.LibAttempt, len(d.Lib))
	}
	if d.LibErr != "" || d.LibNote != "" {
		t.Fatalf("libErr=%q libNote=%q", d.LibErr, d.LibNote)
	}
	if d.Python == "" || d.PythonErr != "" || d.PythonChanged {
		t.Fatalf("python err=%q changed=%v len=%d", d.PythonErr, d.PythonChanged, len(d.Python))
	}
	if len(d.Attempts) != 1 || d.Attempts[0].Outcome != "ACCEPTED" {
		t.Fatalf("attempts = %+v", d.Attempts)
	}
	if len(d.Diff) == 0 {
		t.Fatal("accepted run must compose the view-only diff")
	}
	joined := strings.Join(d.Diff, "\n")
	for _, want := range []string{
		"# smelt apply — 261011-015326-a41353 · VIEW ONLY (nothing is written)",
		"# target : source/run_length.py:rle_encode",
		"--- /dev/null",
		"+++ rust/rle_encode/src/lib.rs",
		"+use pyo3::prelude::*;",
		"maturin develop --release",
		"from rust.rle_encode import rle_encode as _fast",
		"## revert",
	} {
		if !strings.Contains(joined, want) {
			t.Errorf("diff missing %q", want)
		}
	}
	if strings.Contains(joined, "/home/") {
		t.Error("diff must not leak absolute paths")
	}
}

func TestResultRejected(t *testing.T) {
	d := loadResult(t, "rejected-gemini")
	if d.Status != "rejected" {
		t.Fatalf("status = %q", d.Status)
	}
	if d.LibAttempt != 3 {
		t.Fatalf("final attempt = %d, want 3 (the last candidate)", d.LibAttempt)
	}
	if !strings.Contains(d.Lib, "fn linear_score") {
		t.Fatalf("lib: %q", d.Lib)
	}
	if len(d.Attempts) != 3 {
		t.Fatalf("attempts = %d", len(d.Attempts))
	}
	for i, a := range d.Attempts {
		if !strings.HasPrefix(a.Outcome, "reject_no_meaningful_gain") {
			t.Errorf("attempt %d outcome = %q", i+1, a.Outcome)
		}
	}
	if len(d.Diff) != 0 {
		t.Error("rejected runs carry nothing to apply")
	}
	if !strings.Contains(d.DiffNote, "is 'rejected' — nothing to apply") {
		t.Fatalf("diff note = %q", d.DiffNote)
	}
}

func TestResultRefused(t *testing.T) {
	d := loadResult(t, "refused-gemini")
	if d.Status != "refused" {
		t.Fatalf("status = %q", d.Status)
	}
	if d.Lib != "" || len(d.Attempts) != 0 {
		t.Fatalf("refused must not carry attempts (attempts=%d)", len(d.Attempts))
	}
	if !strings.Contains(d.LibErr, "refused before generation") {
		t.Fatalf("libErr = %q", d.LibErr)
	}
	if !strings.Contains(d.Refusal, "module imports 'random'") {
		t.Fatalf("refusal = %q", d.Refusal)
	}
	if d.RefusalHint != "" {
		t.Fatalf("impure refusal carries no hint, got %q", d.RefusalHint)
	}
	if !strings.Contains(d.DiffNote, "smelt apply: run") {
		t.Fatalf("diff note = %q", d.DiffNote)
	}
}

func TestResultRefusalHintSplit(t *testing.T) {
	d := loadResult(t, "refused-hint-gemini")
	if d.Status != "refused" {
		t.Fatalf("status = %q", d.Status)
	}
	if strings.Contains(d.Refusal, "refactor hint") {
		t.Fatalf("hint must be split out of the reason: %q", d.Refusal)
	}
	if !strings.Contains(d.Refusal, "relative import") {
		t.Fatalf("reason = %q", d.Refusal)
	}
	if !strings.Contains(d.RefusalHint, "point smelt at a standalone module") {
		t.Fatalf("hint = %q", d.RefusalHint)
	}
	if d.Provider != "gemini" || d.Model != "gemma-4-26b-a4b-it" {
		t.Fatalf("provider/model = %q/%q", d.Provider, d.Model)
	}
}

func TestResultMismatchSample(t *testing.T) {
	d := loadResult(t, "mismatch-file")
	if len(d.Attempts) != 3 {
		t.Fatalf("attempts = %d", len(d.Attempts))
	}
	a := d.Attempts[0]
	if a.Sample == nil {
		t.Fatal("first attempt has no parsed sample")
	}
	if a.Sample.CaseID != "e0074" {
		t.Fatalf("case = %q", a.Sample.CaseID)
	}
	if len(a.Sample.Args) != 2 || a.Sample.Args[0] != "-9223372036854775808" || a.Sample.Args[1] != "-1" {
		t.Fatalf("args = %v (big ints must survive the decode)", a.Sample.Args)
	}
	if a.Sample.Want != "int 9223372036854775808" {
		t.Fatalf("want = %q", a.Sample.Want)
	}
	if !strings.Contains(a.Sample.Got, "PanicException") {
		t.Fatalf("got = %q", a.Sample.Got)
	}
	strip := strings.Join(stripAttemptLines(a), "\n")
	for _, want := range []string{
		"✗ mismatch · e0074",
		"in [-9223372036854775808 -1]",
		"want int 9223372036854775808",
		"got PanicException",
	} {
		if !strings.Contains(strip, want) {
			t.Errorf("strip missing %q:\n%s", want, strip)
		}
	}
}

func TestResultMissingArtifacts(t *testing.T) {
	d := loadResult(t, "missing-artifacts")
	if d.Status != "accepted" {
		t.Fatalf("status = %q", d.Status)
	}
	if d.Lib != "" {
		t.Fatal("fixture has attempts/ removed")
	}
	if !strings.Contains(d.LibErr, "attempts/it1/lib.rs is missing") {
		t.Fatalf("libErr = %q", d.LibErr)
	}
	if !strings.Contains(d.DiffNote, "candidate lib.rs not found in the run dir") {
		t.Fatalf("diffNote = %q", d.DiffNote)
	}
	if len(d.Attempts) != 1 {
		t.Fatalf("attempts = %d (from state.json)", len(d.Attempts))
	}
}

func TestResultStripFeedbackLoop(t *testing.T) {
	d := loadResult(t, "rejected-gemini")
	m := New(&RunSummary{Dir: fixturesDir + "/rejected-gemini"})
	m.Res = &ResultState{Data: d}
	m.Width, m.Height = 120, 40
	strip := strings.Join(m.resultStrip(), "\n")
	if !strings.Contains(strip, "attempts  1 ◇ no gain · ratio 1.47x, lower bound 1.42x") {
		t.Errorf("strip:\n%s", strip)
	}
	if !strings.Contains(strip, "3 ◇ no gain · ratio 1.41x, lower bound 1.37x") {
		t.Errorf("strip:\n%s", strip)
	}
}

func TestResultToggleAndEsc(t *testing.T) {
	s := load(t, "accepted-gemini")
	m := New(s)
	m.Update(tea.WindowSizeMsg{Width: 100, Height: 30})
	m.Update(keyRunes('r'))
	if !m.ResultOpen() {
		t.Fatal("r did not open the Result screen")
	}
	m.Update(keyRunes('r'))
	if m.ResultOpen() {
		t.Fatal("r did not close the Result screen")
	}
	m.Update(keyRunes('r'))
	m.Update(tea.KeyMsg{Type: tea.KeyEscape})
	if m.ResultOpen() {
		t.Fatal("esc did not close the Result screen")
	}
}

// GATE: the Result screen must fit an 80-column terminal on every tab, for
// every fixture (missing artifacts included).
func TestResultViewFits80(t *testing.T) {
	for _, fx := range []string{
		"accepted-gemini", "rejected-gemini", "refused-gemini",
		"refused-hint-gemini", "mismatch-file", "missing-artifacts",
		"unit-file-provider",
	} {
		s := load(t, fx)
		m := New(s)
		m.Update(tea.WindowSizeMsg{Width: 80, Height: 24})
		m.openResult()
		if !m.ResultOpen() {
			t.Fatalf("%s: result did not open", fx)
		}
		for tab := 0; tab < len(resultTabs); tab++ {
			m.Res.Tab = tab
			for _, ln := range strings.Split(m.View(), "\n") {
				if lipgloss.Width(ln) > 80 {
					t.Fatalf("%s tab %d: line over 80 cols (%d): %q", fx, tab, lipgloss.Width(ln), ln)
				}
			}
		}
	}
}

func TestResultSmallNoPanic(t *testing.T) {
	s := load(t, "mismatch-file")
	m := New(s)
	for _, size := range [][2]int{{40, 12}, {60, 20}, {200, 60}, {80, 24}} {
		m.Update(tea.WindowSizeMsg{Width: size[0], Height: size[1]})
		m.openResult()
		for _, ln := range strings.Split(m.View(), "\n") {
			if lipgloss.Width(ln) > size[0] {
				t.Fatalf("%dx%d: line over cols: %q", size[0], size[1], ln)
			}
		}
	}
}
