package replay

import (
	"strings"

	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
)

// Model is the replay viewer. Keyboard: q quits, tab switches panes,
// up/down (and pgup/pgdn) scroll the log when it is focused.
type Model struct {
	Sum    *RunSummary
	Width  int
	Height int
	Focus  int // 0 = results, 1 = log
	LogVP  viewport.Model
	ready  bool
}

// New builds the viewer for a loaded run.
func New(sum *RunSummary) *Model {
	return &Model{Sum: sum, Width: 100, Height: 30}
}

func (m *Model) Init() tea.Cmd { return nil }

func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.Width, m.Height = msg.Width, msg.Height
		m.layout()
		return m, nil
	case tea.KeyMsg:
		switch msg.String() {
		case "q", "ctrl+c", "esc":
			return m, tea.Quit
		case "tab":
			m.Focus = (m.Focus + 1) % 2
			return m, nil
		}
		if m.Focus == 1 && m.ready {
			var cmd tea.Cmd
			m.LogVP, cmd = m.LogVP.Update(msg)
			return m, cmd
		}
		return m, nil
	}
	return m, nil
}

func (m *Model) layout() {
	logH := m.Height - 16
	if logH < 3 {
		logH = 3
	}
	w := m.Width - 6
	if w < 10 {
		w = 10
	}
	if !m.ready {
		m.LogVP = viewport.New(w, logH)
		m.LogVP.SetContent(strings.Join(m.Sum.Log, "\n"))
		m.ready = true
	} else {
		m.LogVP.Width = w
		m.LogVP.Height = logH
	}
}
