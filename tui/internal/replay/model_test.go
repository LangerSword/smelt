package replay

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/muesli/termenv"
)

func TestMain(m *testing.M) {
	// Deterministic, colour-free rendering for tests and goldens.
	lipgloss.SetColorProfile(termenv.Ascii)
	os.Exit(m.Run())
}

const fixturesDir = "../../testdata/runs"

func load(t *testing.T, name string) *RunSummary {
	t.Helper()
	s, err := LoadRun(filepath.Join(fixturesDir, name))
	if err != nil {
		t.Fatalf("LoadRun(%s): %v", name, err)
	}
	return s
}

func almost(a, b float64) bool {
	d := a - b
	if d < 0 {
		d = -d
	}
	return d < 0.005
}

// The three Gemini fixtures are REAL runs (see testdata/runs/README.md).

func TestLoadAcceptedGemini(t *testing.T) {
	s := load(t, "accepted-gemini")
	if s.Status != "accepted" {
		t.Fatalf("status = %q", s.Status)
	}
	if s.Provider != "gemini" || s.Model != "gemma-4-26b-a4b-it" {
		t.Fatalf("provider/model = %q/%q", s.Provider, s.Model)
	}
	if s.NCases != 225 || s.Attempts != 1 {
		t.Fatalf("cases=%d attempts=%d", s.NCases, s.Attempts)
	}
	if !s.HasSpeedup || !s.HasLB || !almost(s.Speedup, 4.14) || !almost(s.SpeedupLB, 4.00) {
		t.Fatalf("speedup=%v lb=%v has=%v/%v", s.Speedup, s.SpeedupLB, s.HasSpeedup, s.HasLB)
	}
}

func TestLoadRejectedGemini(t *testing.T) {
	s := load(t, "rejected-gemini")
	if s.Status != "rejected" {
		t.Fatalf("status = %q", s.Status)
	}
	if s.Attempts != 3 {
		t.Fatalf("attempts = %d", s.Attempts)
	}
	if !s.HasSpeedup || !almost(s.Speedup, 1.41) || !almost(s.SpeedupLB, 1.37) {
		t.Fatalf("speedup=%v lb=%v", s.Speedup, s.SpeedupLB)
	}
	if !strings.Contains(strings.Join(s.Log, "\n"), "reject ·") {
		t.Fatalf("log missing reject line: %v", s.Log)
	}
}

func TestLoadRefusedGemini(t *testing.T) {
	s := load(t, "refused-gemini")
	if s.Status != "refused" {
		t.Fatalf("status = %q", s.Status)
	}
	if s.Attempts != 0 {
		t.Fatalf("attempts = %d", s.Attempts)
	}
	if s.HasSpeedup {
		t.Fatal("refused run must not carry a speedup")
	}
	if !strings.Contains(strings.Join(s.Log, "\n"), "refused_impure") {
		t.Fatalf("log: %v", s.Log)
	}
	if s.Provider != "gemini" || s.Model != "gemma-4-26b-a4b-it" {
		t.Fatalf("provider/model = %q/%q", s.Provider, s.Model)
	}
}

func TestLoadUnitFileProvider(t *testing.T) {
	s := load(t, "unit-file-provider")
	if s.Status != "accepted" {
		t.Fatalf("status = %q", s.Status)
	}
	if s.Provider != "file" || s.Model != "" {
		t.Fatalf("provider/model = %q/%q", s.Provider, s.Model)
	}
	if !s.HasLB || !almost(s.Speedup, 3.28) || !almost(s.SpeedupLB, 3.25) {
		t.Fatalf("speedup=%v lb=%v", s.Speedup, s.SpeedupLB)
	}
}

func TestBadLineSkippedAndCounted(t *testing.T) {
	srcDir := filepath.Join(fixturesDir, "accepted-gemini")
	ev, err := os.ReadFile(filepath.Join(srcDir, "events.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	st, _ := os.ReadFile(filepath.Join(srcDir, "state.json"))
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "events.jsonl"), append(ev, []byte("{not json\n")...), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "state.json"), st, 0o644); err != nil {
		t.Fatal(err)
	}
	s, err := LoadRun(dir)
	if err != nil {
		t.Fatalf("LoadRun: %v", err)
	}
	if s.BadLines != 1 {
		t.Fatalf("bad lines = %d, want 1", s.BadLines)
	}
	if s.Status != "accepted" {
		t.Fatalf("status = %q", s.Status)
	}
}

func viewLines(t *testing.T, s *RunSummary, w, h int) []string {
	t.Helper()
	m := New(s)
	m.Update(tea.WindowSizeMsg{Width: w, Height: h})
	return strings.Split(m.View(), "\n")
}

// GATE: narrow terminal (80 columns) must not break layout.
func TestViewFits80Columns(t *testing.T) {
	for _, fx := range []string{"accepted-gemini", "rejected-gemini", "refused-gemini", "unit-file-provider"} {
		s := load(t, fx)
		lines := viewLines(t, s, 80, 24)
		for _, ln := range lines {
			if lipgloss.Width(ln) > 80 {
				t.Fatalf("%s: line over 80 cols (%d): %q", fx, lipgloss.Width(ln), ln)
			}
		}
		whole := strings.Join(lines, "\n")
		for _, n := range FlowNodes {
			if !strings.Contains(whole, n) {
				t.Fatalf("%s: flow node %q missing", fx, n)
			}
		}
		if !strings.Contains(whole, "VERDICT:") || !strings.Contains(whole, "speedup") {
			t.Fatalf("%s: required panels missing", fx)
		}
	}
}

func TestViewSmallNoPanic(t *testing.T) {
	for _, fx := range []string{"accepted-gemini", "refused-gemini"} {
		s := load(t, fx)
		for _, ln := range viewLines(t, s, 40, 12) {
			if lipgloss.Width(ln) > 40 {
				t.Fatalf("%s: line over 40 cols: %q", fx, ln)
			}
		}
	}
}

func TestVerdictMapping(t *testing.T) {
	want := map[string]string{
		"accepted": "INGOT", "rejected": "SLAG", "refused": "ASH",
		"error": "ASH", "in_progress": "COLD",
	}
	for st, w := range want {
		got, _ := Verdict(st)
		if got != w {
			t.Fatalf("Verdict(%q) = %q, want %q", st, got, w)
		}
	}
}

func TestDisplayModelHonesty(t *testing.T) {
	if DisplayModel("file", "") != "— (no model: file fixture)" {
		t.Fatal("file fixture must be labelled as model-free")
	}
	if DisplayModel("gemini", "gemma-4-26b-a4b-it") != "gemma-4-26b-a4b-it" {
		t.Fatal("real models must be labelled with their name")
	}
}
