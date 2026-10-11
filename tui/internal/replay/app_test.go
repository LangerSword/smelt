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

// App (home screen) tests, driven by the fake smelt (scan/doctor/apply/run).

func startFakeApp(t *testing.T, env map[string]string) *App {
	t.Helper()
	dir := t.TempDir()
	runsDir := filepath.Join(dir, "runs")
	t.Setenv("FAKE_RUNS_DIR", runsDir)
	for k, v := range env {
		t.Setenv(k, v)
	}
	return NewApp(fakeSmeltPath(t), runsDir)
}

func typeText(tm *teatest.TestModel, s string) {
	for _, r := range s {
		tm.Send(keyRunes(r))
	}
}

func contains(s string) func([]byte) bool {
	return func(out []byte) bool { return bytes.Contains(out, []byte(s)) }
}

func TestAppHelpThenQuit(t *testing.T) {
	app := startFakeApp(t, nil)
	tm := teatest.NewTestModel(t, app, teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(), contains("smelt home"), teatest.WithDuration(5*time.Second))

	typeText(tm, "/help")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	teatest.WaitFor(t, tm.Output(), contains("/scan <path>"), teatest.WithDuration(5*time.Second))

	tm.Send(tea.KeyMsg{Type: tea.KeyEscape}) // back to home
	typeText(tm, "/quit")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

	fin := tm.FinalModel(t).(*App)
	if fin.Screen != ScreenHome {
		t.Fatalf("screen = %v, want home after esc", fin.Screen)
	}
}

func TestAppScanPickAndRun(t *testing.T) {
	app := startFakeApp(t, map[string]string{"FAKE_SLEEP": "0"})
	tm := teatest.NewTestModel(t, app, teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(), contains("smelt home"), teatest.WithDuration(5*time.Second))

	typeText(tm, "/scan demo")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	// scan results land; the candidate list shows the fake function + skip reason
	teatest.WaitFor(t, tm.Output(), contains("fake_fn"), teatest.WithDuration(5*time.Second))

	tm.Send(tea.KeyMsg{Type: tea.KeyEnter}) // focus moved to candidates; run it
	teatest.WaitFor(t, tm.Output(), contains("INGOT"), teatest.WithDuration(12*time.Second))

	tm.Send(tea.KeyMsg{Type: tea.KeyEscape}) // back to home
	typeText(tm, "/quit")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

	fin := tm.FinalModel(t).(*App)
	if fin.Screen != ScreenHome {
		t.Fatalf("screen = %v, want home", fin.Screen)
	}
	if fin.Run == nil || !fin.Run.Done || fin.Run.Sum.Status != "accepted" {
		t.Fatalf("run state wrong: %+v", fin.Run)
	}
	if fin.Run.Sum.NCases != 42 {
		t.Fatalf("oracle cases = %d", fin.Run.Sum.NCases)
	}
	// the scan root must be joined into the run target (regression: relative-path bug)
	if !strings.Contains(fin.Run.Sum.Target, "fake/demo/fake.py") {
		t.Fatalf("run target not joined with scan root: %q", fin.Run.Sum.Target)
	}
}

func seedRun(t *testing.T, app *App) {
	t.Helper()
	seed := filepath.Join(app.RunsDir, "261011-015326-a41353")
	if err := os.MkdirAll(seed, 0o755); err != nil {
		t.Fatal(err)
	}
	for _, f := range []string{"events.jsonl", "state.json"} {
		b, err := os.ReadFile(filepath.Join(fixturesDir, "accepted-gemini", f))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(seed, f), b, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	app.loadHistory()
}

func TestAppHistoryResumeAndDiff(t *testing.T) {
	app := startFakeApp(t, nil)
	seedRun(t, app)

	tm := teatest.NewTestModel(t, app, teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(), contains("261011-015326-a41353"), teatest.WithDuration(5*time.Second))

	tm.Send(tea.KeyMsg{Type: tea.KeyTab})   // focus candidates
	tm.Send(tea.KeyMsg{Type: tea.KeyTab})   // focus history
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter}) // open the run
	teatest.WaitFor(t, tm.Output(), contains("INGOT"), teatest.WithDuration(5*time.Second))

	tm.Send(keyRunes('d')) // apply (view only)
	teatest.WaitFor(t, tm.Output(), contains("VIEW ONLY"), teatest.WithDuration(5*time.Second))

	tm.Send(tea.KeyMsg{Type: tea.KeyEscape})
	typeText(tm, "/quit")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))
}

func TestAppDoctorPane(t *testing.T) {
	app := startFakeApp(t, nil)
	tm := teatest.NewTestModel(t, app, teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(), contains("smelt home"), teatest.WithDuration(5*time.Second))

	typeText(tm, "/doctor")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	teatest.WaitFor(t, tm.Output(), contains("gemini key"), teatest.WithDuration(5*time.Second))

	tm.Send(tea.KeyMsg{Type: tea.KeyEscape})
	typeText(tm, "/quit")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))
}

func TestAppUnknownCommandShowsStatus(t *testing.T) {
	app := startFakeApp(t, nil)
	tm := teatest.NewTestModel(t, app, teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(), contains("smelt home"), teatest.WithDuration(5*time.Second))

	typeText(tm, "/nope")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	teatest.WaitFor(t, tm.Output(), contains("unknown command"), teatest.WithDuration(5*time.Second))

	typeText(tm, "/quit")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))
}

func TestAppHomeFits80Columns(t *testing.T) {
	app := startFakeApp(t, nil)
	app.Update(tea.WindowSizeMsg{Width: 80, Height: 24})
	for _, ln := range splitView2(app.View()) {
		if len([]rune(ln)) > 80 {
			t.Fatalf("home line over 80 cols: %q", ln)
		}
	}
}

// GATE: the help overlay (U4).
func TestAppHelpOverlay(t *testing.T) {
	app := startFakeApp(t, nil)
	tm := teatest.NewTestModel(t, app, teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(), contains("smelt home"), teatest.WithDuration(5*time.Second))

	tm.Send(keyRunes('?'))
	teatest.WaitFor(t, tm.Output(), contains("/sessions"), teatest.WithDuration(5*time.Second))
	tm.Send(tea.KeyMsg{Type: tea.KeyEscape})

	typeText(tm, "/quit")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))
}

// GATE: the command autocomplete panel (U3) — typing /se lists matches,
// tab completes to the selected command, enter runs it.
func TestAppAutocompletePanel(t *testing.T) {
	app := startFakeApp(t, nil)
	tm := teatest.NewTestModel(t, app, teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(), contains("smelt home"), teatest.WithDuration(5*time.Second))

	typeText(tm, "/se")
	teatest.WaitFor(t, tm.Output(), contains("run history picker"), teatest.WithDuration(5*time.Second))
	tm.Send(tea.KeyMsg{Type: tea.KeyTab})   // completes to "/sessions "
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter}) // opens the sessions picker
	teatest.WaitFor(t, tm.Output(), contains("run history"), teatest.WithDuration(5*time.Second))
	tm.Send(tea.KeyMsg{Type: tea.KeyEscape})

	typeText(tm, "/quit")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	tm.WaitFinished(t, teatest.WithFinalTimeout(3*time.Second))

	fin := tm.FinalModel(t).(*App)
	if !strings.Contains(strings.Join(fin.Prompts, " "), "/sessions") {
		t.Fatalf("prompt history missing /sessions: %v", fin.Prompts)
	}
}

// GATE: a killed run (U3) — ctrl+c once stops with a confirm line, twice quits;
// the run is marked stopped-by-user and stays resumable.
func TestAppCtrlCStopsRun(t *testing.T) {
	app := startFakeApp(t, map[string]string{"FAKE_SLEEP": "3"})
	tm := teatest.NewTestModel(t, app, teatest.WithInitialTermSize(100, 30))
	teatest.WaitFor(t, tm.Output(), contains("smelt home"), teatest.WithDuration(5*time.Second))

	typeText(tm, "/run fake/demo/fake.py:fake_fn")
	tm.Send(tea.KeyMsg{Type: tea.KeyEnter})
	teatest.WaitFor(t, tm.Output(), contains("FURNACE v"), teatest.WithDuration(5*time.Second))

	tm.Send(tea.KeyMsg{Type: tea.KeyCtrlC})
	teatest.WaitFor(t, tm.Output(), contains("stopped — ctrl+c again"), teatest.WithDuration(5*time.Second))
	tm.Send(tea.KeyMsg{Type: tea.KeyCtrlC})
	tm.WaitFinished(t, teatest.WithFinalTimeout(5*time.Second))

	fin := tm.FinalModel(t).(*App)
	if fin.Run == nil || !fin.Run.KilledByUser {
		t.Fatalf("run not marked killed-by-user: %+v", fin.Run)
	}
}

func splitView2(s string) []string {
	return strings.Split(s, "\n")
}
