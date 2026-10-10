// furnace — read-only TUI for smelt runs.
//
//	furnace replay <run-dir>
//
// Reads runs/<id>/events.jsonl (+ state.json) and renders the loop, the
// results panel, the log pane and the final verdict (INGOT / SLAG / ASH).
package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/LangerSword/smelt/tui/internal/replay"
)

func main() {
	args := os.Args[1:]
	if len(args) != 2 || args[0] != "replay" {
		fmt.Fprintln(os.Stderr, "usage: furnace replay <run-dir>")
		fmt.Fprintln(os.Stderr, "  <run-dir> is a smelt run directory containing events.jsonl + state.json")
		os.Exit(2)
	}
	sum, err := replay.LoadRun(args[1])
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
