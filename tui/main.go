// furnace — terminal UI for smelt runs.
//
//	furnace replay <run-dir>            replay a finished run
//	furnace run <file.py:fn> [flags]    run smelt live and watch it
//
// Furnace is a front end. It reads runs/<id>/events.jsonl (+ state.json) and
// starts runs with `smelt run ... --json` as a subprocess. It never runs
// generated code and never reads or prints secrets.
package main

import (
	"fmt"
	"os"
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/LangerSword/smelt/tui/internal/replay"
)

const usage = `usage:
  furnace [--no-anim]                      home screen: scan · pick · run · history
  furnace replay <run-dir>                 replay a finished run (q quit · tab panes · ↑/↓ scroll)
  furnace run <file.py:fn> [flags]         run smelt live and watch it

flags for run:
  --provider <name>   provider passed to smelt (default "gemini")
  --model <name>      model passed to smelt (default: provider default, e.g. gemma-4-26b-a4b-it)
  --smelt <path>      smelt binary (default: found on PATH)
  --runs-dir <dir>    where smelt writes runs (default "runs")`

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		homeCmd(false)
		return
	}
	if args[0] == "--no-anim" {
		homeCmd(true)
		return
	}
	switch args[0] {
	case "replay":
		if len(args) != 2 {
			fmt.Fprintln(os.Stderr, usage)
			os.Exit(2)
		}
		replayCmd(args[1])
	case "run":
		runCmd(args[1:])
	default:
		fmt.Fprintln(os.Stderr, usage)
		os.Exit(2)
	}
}

func replayCmd(dir string) {
	sum, err := replay.LoadRun(dir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "furnace: %v\n", err)
		os.Exit(1)
	}
	p := tea.NewProgram(replay.New(sum), tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "furnace: %v\n", err)
		os.Exit(1)
	}
}

func runCmd(args []string) {
	target, provider, model, smeltBin, runsDir := "", "gemini", "", "", "runs"
	noAnim := false
	for i := 0; i < len(args); i++ {
		need := func(flag string) string {
			i++
			if i >= len(args) {
				fail(flag + " needs a value")
			}
			return args[i]
		}
		switch args[i] {
		case "--no-anim":
			noAnim = true
		case "--provider":
			provider = need("--provider")
		case "--model":
			model = need("--model")
		case "--smelt":
			smeltBin = need("--smelt")
		case "--runs-dir":
			runsDir = need("--runs-dir")
		default:
			if strings.HasPrefix(args[i], "-") {
				fail("unknown flag " + args[i])
			}
			if target != "" {
				fail("unexpected extra argument " + args[i])
			}
			target = args[i]
		}
	}
	if target == "" {
		fail("furnace run needs a target: file.py:function")
	}
	bin, err := replay.ResolveSmelt(smeltBin)
	if err != nil {
		fmt.Fprintln(os.Stderr, "furnace: smelt binary not found.")
		fmt.Fprintln(os.Stderr, "  install smelt, or pass --smelt /path/to/smelt")
		fmt.Fprintln(os.Stderr, "  (in the smelt repo: --smelt .venv/bin/smelt)")
		os.Exit(2)
	}
	live, err := replay.StartLive(bin, target, provider, model, runsDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "furnace: could not start smelt: %v\n", err)
		os.Exit(1)
	}
	sum := &replay.RunSummary{Dir: runsDir, Status: "in_progress"}
	m := replay.NewLive(sum, live)
	m.Anim = animEnabled(noAnim)
	p := tea.NewProgram(m, tea.WithAltScreen())
	final, runErr := p.Run()
	if runErr != nil {
		fmt.Fprintf(os.Stderr, "furnace: %v\n", runErr)
		os.Exit(1)
	}
	m, ok := final.(*replay.Model)
	if !ok {
		return
	}
	switch {
	case m.KilledByUser:
		fmt.Println("furnace: stopped by user — run left in progress; resume with:")
		fmt.Printf("  smelt resume %s\n", m.RunDirForReport(runsDir))
	case m.Done && m.ExitCode != 0:
		fmt.Printf("furnace: smelt exited with code %d — see the log pane and the run directory\n", m.ExitCode)
	case m.Done:
		fmt.Printf("furnace: smelt finished (%s)\n", m.Sum.Status)
	}
}

// animEnabled reports whether the heat-pulse animation should run: off with
// --no-anim, with NO_COLOR set, or on a dumb terminal.
func animEnabled(noAnim bool) bool {
	if noAnim || os.Getenv("NO_COLOR") != "" || os.Getenv("TERM") == "dumb" {
		return false
	}
	return true
}

func homeCmd(noAnim bool) {
	bin, err := replay.ResolveSmelt("")
	if err != nil {
		fmt.Fprintln(os.Stderr, "furnace: smelt binary not found on PATH.")
		fmt.Fprintln(os.Stderr, "  install smelt, or run: furnace run <target> --smelt /path/to/smelt")
		os.Exit(2)
	}
	app := replay.NewApp(bin, "runs")
	app.Anim = animEnabled(noAnim)
	p := tea.NewProgram(app, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "furnace: %v\n", err)
		os.Exit(1)
	}
}

func fail(msg string) {
	fmt.Fprintln(os.Stderr, "furnace: "+msg)
	fmt.Fprintln(os.Stderr, usage)
	os.Exit(2)
}
