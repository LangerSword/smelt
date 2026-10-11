package replay

import (
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/x/exp/golden"
	"github.com/charmbracelet/x/exp/teatest"
)

// Golden tests for the Result screen (r; auto-opened after accepted/rejected
// live runs). Fixtures are real run slices — provenance in
// testdata/runs/README.md.
//
// Regenerate with: go test ./internal/replay -update

func runResultGolden(t *testing.T, fixture string, tab, w, h int, wait string) {
	t.Helper()
	sum, err := LoadRun(fixturesDir + "/" + fixture)
	if err != nil {
		t.Fatalf("LoadRun(%s): %v", fixture, err)
	}
	tm := teatest.NewTestModel(t, New(sum), teatest.WithInitialTermSize(w, h))
	teatest.WaitFor(t, tm.Output(), contains(wait), teatest.WithDuration(3*time.Second))

	tm.Send(keyRunes('r')) // open the Result screen
	teatest.WaitFor(t, tm.Output(), contains("[1 summary]"), teatest.WithDuration(3*time.Second))
	for i := 0; i < tab; i++ {
		tm.Send(tea.KeyMsg{Type: tea.KeyRight})
	}
	tm.Send(keyRunes('q'))
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

	fin := tm.FinalModel(t).(*Model)
	if !fin.ResultOpen() {
		t.Fatalf("%s: the Result screen is not open", fixture)
	}
	if fin.Res.Tab != tab {
		t.Fatalf("%s: tab = %d, want %d", fixture, fin.Res.Tab, tab)
	}
	golden.RequireEqual(t, []byte(fin.View()))
}

// GATE: accepted / rejected / refused fixtures at 80x24 and 120x40.
func TestResultAccepted80x24(t *testing.T) {
	runResultGolden(t, "accepted-gemini", 0, 80, 24, "INGOT")
}

func TestResultAccepted120x40(t *testing.T) {
	runResultGolden(t, "accepted-gemini", 0, 120, 40, "INGOT")
}

func TestResultRejected80x24(t *testing.T) {
	runResultGolden(t, "rejected-gemini", 0, 80, 24, "SLAG")
}

func TestResultRejected120x40(t *testing.T) {
	runResultGolden(t, "rejected-gemini", 0, 120, 40, "SLAG")
}

func TestResultRefused80x24(t *testing.T) {
	runResultGolden(t, "refused-gemini", 0, 80, 24, "ASH")
}

func TestResultRefused120x40(t *testing.T) {
	runResultGolden(t, "refused-gemini", 0, 120, 40, "ASH")
}

// GATE: the missing-artifact case (attempts/ pruned) must render clearly.
func TestResultMissingArtifacts80x24(t *testing.T) {
	runResultGolden(t, "missing-artifacts", 0, 80, 24, "INGOT")
}

func TestResultMissingArtifactsRust80x24(t *testing.T) {
	runResultGolden(t, "missing-artifacts", 1, 80, 24, "INGOT")
}

// RUST tab: accepted candidate with line numbers; SLAG marked rejected;
// ASH shows the refusal reason + refactor hint.
func TestResultAcceptedRust120x40(t *testing.T) {
	runResultGolden(t, "accepted-gemini", 1, 120, 40, "INGOT")
}

func TestResultRejectedRust80x24(t *testing.T) {
	runResultGolden(t, "rejected-gemini", 1, 80, 24, "SLAG")
}

func TestResultRefusedHintRust80x24(t *testing.T) {
	runResultGolden(t, "refused-hint-gemini", 1, 80, 24, "ASH")
}

// COMPARE tab: two columns at >=120, stacked below; one viewport.
func TestResultAcceptedCompare120x40(t *testing.T) {
	runResultGolden(t, "accepted-gemini", 2, 120, 40, "INGOT")
}

func TestResultRejectedCompare80x24(t *testing.T) {
	runResultGolden(t, "rejected-gemini", 2, 80, 24, "SLAG")
}

// DIFF tab: the view-only apply diff (+/- colouring) and its refusal notes.
func TestResultAcceptedDiff80x24(t *testing.T) {
	runResultGolden(t, "accepted-gemini", 3, 80, 24, "INGOT")
}

func TestResultMissingArtifactsDiff80x24(t *testing.T) {
	runResultGolden(t, "missing-artifacts", 3, 80, 24, "INGOT")
}
