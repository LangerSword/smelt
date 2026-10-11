package replay

import (
	"bytes"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/x/exp/golden"
	"github.com/charmbracelet/x/exp/teatest"
)

// Golden tests for the replay viewer, driven by teatest.
//
// Fixtures (see testdata/runs/README.md):
//   - accepted / rejected / refused: REAL gemini runs (gemma-4-26b-a4b-it)
//   - unit-file-provider: fast file-provider fixture (no model)
//
// Regenerate goldens with:  go test ./internal/replay -update

func keyRunes(r rune) tea.KeyMsg { return tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}} }

func runReplayTeatest(t *testing.T, fixture string, w, h int, wait string) {
	t.Helper()
	sum, err := LoadRun(fixturesDir + "/" + fixture)
	if err != nil {
		t.Fatalf("LoadRun(%s): %v", fixture, err)
	}
	tm := teatest.NewTestModel(t, New(sum), teatest.WithInitialTermSize(w, h))
	teatest.WaitFor(t, tm.Output(),
		func(b []byte) bool { return bytes.Contains(b, []byte(wait)) },
		teatest.WithDuration(3*time.Second))

	// Exercise the keys: tab (pane focus), down/up (scroll), q (quit).
	tm.Send(tea.KeyMsg{Type: tea.KeyTab})
	tm.Send(tea.KeyMsg{Type: tea.KeyDown})
	tm.Send(tea.KeyMsg{Type: tea.KeyUp})
	tm.Send(keyRunes('q'))
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

	// Golden the final rendered frame. The live stream is drained by WaitFor
	// (teatest keeps only the unread tail) and FinalModel only returns once
	// the program finished — so the complete, deterministic frame comes from
	// the final model after quit. Same mechanism as teatest.RequireEqualOutput
	// (which is golden.RequireEqual underneath).
	fin := tm.FinalModel(t)
	m, ok := fin.(*Model)
	if !ok {
		t.Fatalf("final model type %T", fin)
	}
	if m.Focus != 1 {
		t.Fatalf("%s: tab did not switch focus (%d)", fixture, m.Focus)
	}
	golden.RequireEqual(t, []byte(m.View()))
}

func TestReplayAcceptedGemini(t *testing.T) {
	runReplayTeatest(t, "accepted-gemini", 100, 30, "INGOT")
}

func TestReplayRejectedGemini(t *testing.T) {
	runReplayTeatest(t, "rejected-gemini", 100, 30, "SLAG")
}

func TestReplayRefusedGemini(t *testing.T) {
	runReplayTeatest(t, "refused-gemini", 100, 30, "ASH")
}

func TestReplayUnitFileProvider(t *testing.T) {
	runReplayTeatest(t, "unit-file-provider", 100, 30, "INGOT")
}

// GATE: the 80-column terminal is a required case.
func TestReplay80ColsRefused(t *testing.T) {
	runReplayTeatest(t, "refused-gemini", 80, 24, "ASH")
}

// GATE: the 120x40 terminal is a required case (U1 two-column layout).
func TestReplay120x40Accepted(t *testing.T) {
	runReplayTeatest(t, "accepted-gemini", 120, 40, "INGOT")
}

// GATE: resize must never crash — shrink then grow mid-replay.
func TestReplayResizeSafe(t *testing.T) {
	sum, err := LoadRun(fixturesDir + "/accepted-gemini")
	if err != nil {
		t.Fatal(err)
	}
	m := New(sum)
	for _, s := range [][2]int{{80, 24}, {160, 45}, {60, 20}, {200, 60}, {80, 24}} {
		m.Update(tea.WindowSizeMsg{Width: s[0], Height: s[1]})
		if v := m.View(); v == "" {
			t.Fatalf("empty view at %dx%d", s[0], s[1])
		}
	}
}

// Key handling: q must quit (program finishes), tab must switch focus.
func TestReplayTabFocusAndQuit(t *testing.T) {
	sum, err := LoadRun(fixturesDir + "/accepted-gemini")
	if err != nil {
		t.Fatal(err)
	}
	tm := teatest.NewTestModel(t, New(sum), teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(),
		func(b []byte) bool { return bytes.Contains(b, []byte("INGOT")) },
		teatest.WithDuration(3*time.Second))
	tm.Send(tea.KeyMsg{Type: tea.KeyTab})
	tm.Send(keyRunes('q'))
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

	fin := tm.FinalModel(t)
	m, ok := fin.(*Model)
	if !ok {
		t.Fatalf("final model type %T", fin)
	}
	if m.Focus != 1 {
		t.Fatalf("tab did not switch focus: %d", m.Focus)
	}
}
