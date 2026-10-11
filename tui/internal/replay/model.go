package replay

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
)

// Mode distinguishes the replay viewer from the live runner.
type Mode int

const (
	ModeReplay Mode = iota
	ModeLive
)

// Model is the furnace viewer. Keyboard: q quits (during a live run it stops
// the run first), tab switches panes, up/down scroll the log when focused.
type Model struct {
	Sum    *RunSummary
	Mode   Mode
	Live   *LiveRun
	Width  int
	Height int
	Focus  int // 0 = results, 1 = log
	LogVP  viewport.Model
	ready  bool

	// live state
	Started      time.Time
	LastEventAt  time.Time
	WaitingModel bool
	Done         bool
	ExitCode     int
	KilledByUser bool
	SkippedLines int
	CrashNote    string
	Anim         bool // heat-pulse animation (disabled with --no-anim / NO_COLOR)
	pulse        int

	LogLines []string
	ExtraLog []string
}

// New builds the replay viewer for a loaded run.
func New(sum *RunSummary) *Model {
	m := &Model{Sum: sum, Width: 100, Height: 30}
	m.LogLines = sum.Log
	return m
}

// NewLive builds the live viewer around a started subprocess.
func NewLive(sum *RunSummary, live *LiveRun) *Model {
	m := &Model{Sum: sum, Mode: ModeLive, Live: live, Width: 100, Height: 30,
		Started: time.Now(), ExitCode: -1}
	m.LogLines = sum.Log
	return m
}

type tickMsg time.Time

func tickCmd() tea.Cmd {
	return tea.Tick(200*time.Millisecond, func(t time.Time) tea.Msg { return tickMsg(t) })
}

func (m *Model) Init() tea.Cmd {
	if m.Mode == ModeLive {
		return tickCmd()
	}
	return nil
}

func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.Width, m.Height = msg.Width, msg.Height
		m.layout()
		return m, nil
	case tickMsg:
		return m.handleTick()
	case tea.KeyMsg:
		switch msg.String() {
		case "q", "ctrl+c", "esc":
			if m.Mode == ModeLive && !m.Done && m.Live != nil {
				m.Live.Kill()
				m.KilledByUser = true
			}
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

func (m *Model) handleTick() (tea.Model, tea.Cmd) {
	if m.Mode != ModeLive || m.Live == nil || m.Done {
		return m, nil
	}
	events, bad, done, exit := m.Live.Poll()
	for _, ev := range events {
		m.Sum.Events = append(m.Sum.Events, ev)
		m.Sum.consume(ev)
		if ev.Ts > 0 {
			m.LastEventAt = time.Unix(int64(ev.Ts), 0)
		}
	}
	if len(bad) > 0 {
		m.SkippedLines += len(bad)
		for _, b := range bad {
			m.ExtraLog = append(m.ExtraLog, "unparsed line (skipped): "+b)
		}
	}
	if done {
		m.Done = true
		m.ExitCode = exit
		if exit != 0 && !m.KilledByUser {
			m.CrashNote = fmt.Sprintf("smelt exited with code %d", exit)
			m.ExtraLog = append(m.ExtraLog, m.CrashNote)
			for _, ln := range m.Live.StderrTail(3) {
				m.ExtraLog = append(m.ExtraLog, "stderr: "+ln)
			}
		}
		m.refreshLog()
		return m, nil
	}
	if len(events) > 0 || len(bad) > 0 {
		m.refreshLog()
	}
	m.WaitingModel = m.lastEventIsGenerate() && time.Since(m.LastEventAt) > 6*time.Second
	if m.Anim {
		m.pulse++
	}
	return m, tickCmd()
}

func (m *Model) lastEventIsGenerate() bool {
	if len(m.Sum.Events) == 0 {
		return false
	}
	last := m.Sum.Events[len(m.Sum.Events)-1].Event
	return last == "attempt_start" || last == "resume"
}

func (m *Model) refreshLog() {
	lines := m.Sum.buildLog()
	lines = append(lines, m.ExtraLog...)
	m.LogLines = lines
	if m.ready {
		m.LogVP.SetContent(strings.Join(lines, "\n"))
	}
}

func (m *Model) layout() {
	logH := m.Height - 16
	if m.Mode == ModeLive {
		logH--
	}
	if logH < 3 {
		logH = 3
	}
	w := m.Width - 6
	if w < 10 {
		w = 10
	}
	if !m.ready {
		m.LogVP = viewport.New(w, logH)
		m.LogVP.SetContent(strings.Join(m.LogLines, "\n"))
		m.ready = true
	} else {
		m.LogVP.Width = w
		m.LogVP.Height = logH
	}
}

// RunDirForReport returns the live run directory (for the post-exit message).
func (m *Model) RunDirForReport(fallback string) string {
	if m.Live != nil && m.Live.RunDir != "" {
		return m.Live.RunDir
	}
	return fallback
}

// activePhase maps the last event to the phase currently in progress.
func (m *Model) activePhase() string {
	if len(m.Sum.Events) == 0 {
		return "starting"
	}
	last := m.Sum.Events[len(m.Sum.Events)-1].Event
	switch last {
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
	case "accept", "reject_no_meaningful_gain", "run_end", "halt":
		return "verdict"
	}
	return ""
}
