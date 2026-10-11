package replay

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"
)

var (
	colEmber = lipgloss.NewStyle().Foreground(lipgloss.Color("#FF6D3A"))
	colGold  = lipgloss.NewStyle().Foreground(lipgloss.Color("#D4A017"))
	colSlag  = lipgloss.NewStyle().Foreground(lipgloss.Color("#6B7280"))
	colDim   = lipgloss.NewStyle().Foreground(lipgloss.Color("240"))

	borderFocused = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#FF6D3A"))
	borderNormal  = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("240"))
)

// Version is the Furnace build shown in the persistent header.
const Version = "0.7"

// fit truncates s to at most w display columns (ellipsis when cut).
func fit(s string, w int) string {
	if w <= 0 {
		return ""
	}
	if lipgloss.Width(s) <= w {
		return s
	}
	out := []rune(s)
	for len(out) > 0 && lipgloss.Width(string(out))+1 > w {
		out = out[:len(out)-1]
	}
	return string(out) + "…"
}

func fitLines(lines []string, w int) []string {
	out := make([]string, len(lines))
	for i, l := range lines {
		out[i] = fit(l, w)
	}
	return out
}

// View renders the furnace run screen (U1 layout):
//
//	header  (FURNACE vX · run id · provider · model)
//	main    (two columns when width >= 100: flow/verdict/results | live panel)
//	log     (scrollable transcript)
//	status  (state · elapsed · verdict) + keys hint
func (m *Model) View() string {
	if !m.ready {
		m.layout()
	}
	var b strings.Builder
	b.WriteString(m.header() + "\n")
	b.WriteString(m.mainArea() + "\n")
	b.WriteString(m.logPane() + "\n")
	b.WriteString(m.statusLine() + "\n")
	b.WriteString(colDim.Render(fit(" ? help · tab panes · ↑/↓ j/k scroll · d diff · q quit", m.Width-1)))
	return b.String()
}

// header is persistent: name, version, run id, provider and model.
func (m *Model) header() string {
	left := fmt.Sprintf("FURNACE v%s · replay · %s", Version, m.Sum.RunID)
	if m.Mode == ModeLive {
		left = fmt.Sprintf("FURNACE v%s · run · %s", Version, m.liveRunID())
	}
	model := DisplayModel(m.Sum.Provider, m.Sum.Model)
	if m.Mode == ModeLive && m.Sum.Model == "" {
		model = "(provider default)"
	}
	right := fit(m.Sum.Provider+" · "+model, m.Width/2)
	left = fit(left, m.Width-lipgloss.Width(right)-3)
	if left == "" {
		return " " + right
	}
	pad := m.Width - 2 - lipgloss.Width(left) - lipgloss.Width(right)
	if pad < 1 {
		pad = 1
	}
	return " " + left + strings.Repeat(" ", pad) + right
}

// mainArea lays out the two columns (or a stack on narrow terminals).
func (m *Model) mainArea() string {
	if m.Width >= 100 {
		colW := (m.Width - 5) / 2
		left := lipgloss.JoinVertical(lipgloss.Left,
			" "+m.flowLine(), m.verdictBox(), m.resultsBoxW(colW))
		right := m.livePanel(colW)
		return lipgloss.JoinHorizontal(lipgloss.Top, left, "  ", right)
	}
	return strings.Join([]string{
		" " + m.flowLine(),
		m.livePanel(m.Width - 4),
		m.verdictBox(),
	}, "\n")
}

func (m *Model) liveRunID() string {
	if m.Live == nil || m.Live.RunDir == "" {
		return "…"
	}
	if i := strings.LastIndex(m.Live.RunDir, "/"); i >= 0 {
		return m.Live.RunDir[i+1:]
	}
	return m.Live.RunDir
}

// livePanel is the right column: oracle progress bar, attempts, speedup and the
// last build/verify message.
func (m *Model) livePanel(w int) string {
	s := m.Sum
	passed := m.casesPassed()
	bar := progressBar(passed, s.NCases, w-12)
	lines := []string{
		"oracle   " + bar,
		fmt.Sprintf("cases    %d/%d passed", passed, s.NCases),
		fmt.Sprintf("attempts %d", s.Attempts),
	}
	switch {
	case s.HasSpeedup && s.HasLB:
		lines = append(lines, fmt.Sprintf("speedup  %.2fx · lb %.2fx", s.Speedup, s.SpeedupLB))
	case s.HasSpeedup:
		lines = append(lines, fmt.Sprintf("speedup  %.2fx · lb —", s.Speedup))
	default:
		lines = append(lines, "speedup  —")
	}
	lines = append(lines, "last     "+m.lastMessage())
	title := "live"
	if m.Mode != ModeLive || m.Done {
		title = "status"
	}
	body := strings.Join(fitLines(lines, w-4), "\n")
	style := borderNormal
	if m.Width < 100 && m.Focus == 0 {
		style = borderFocused
	}
	return style.Render(fit(title, w-4) + "\n" + body)
}

// progressBar renders a text progress bar (colour never carries meaning).
func progressBar(done, total, w int) string {
	if total <= 0 {
		return "—"
	}
	if w < 10 {
		w = 10
	}
	f := float64(done) / float64(total)
	if f > 1 {
		f = 1
	}
	if f < 0 {
		f = 0
	}
	fill := int(f * float64(w))
	bar := strings.Repeat("█", fill) + strings.Repeat("░", w-fill)
	return fmt.Sprintf("[%s] %3.0f%%", bar, f*100)
}

// casesPassed is the number of oracle cases proven equal (verify pass).
func (m *Model) casesPassed() int {
	s := m.Sum
	if s.HasSpeedup { // accept / reject_no_meaningful_gain both imply verify passed
		return s.NCases
	}
	switch s.Status {
	case "accepted", "rejected":
		return s.NCases
	}
	return 0
}

// lastMessage is the newest transcript line (build/verify/halt news).
func (m *Model) lastMessage() string {
	if n := len(m.LogLines); n > 0 {
		last := m.LogLines[n-1]
		if last != "" {
			return last
		}
	}
	return "—"
}

// statusLine shows state, elapsed time and the verdict word (always labelled).
func (m *Model) statusLine() string {
	state := "done · " + m.Sum.Status
	if m.Mode == ModeLive && !m.Done {
		state = "running · heating"
		if m.WaitingModel {
			sp := "◐"
			if m.Anim {
				sp = []string{"◐", "◓", "◑", "◒"}[m.pulse%4]
			}
			state = "waiting for the model " + sp
		}
	} else if m.Mode == ModeLive && m.KilledByUser {
		state = "done · stopped by user"
	}
	el := ""
	if d := m.eventSpan(); d >= time.Second {
		el = " · " + d.Round(time.Second).String()
	}
	word, _ := Verdict(m.Sum.Status)
	if m.Mode == ModeLive && m.KilledByUser {
		word = "COLD"
	}
	return colDim.Render(fit(fmt.Sprintf(" %s%s · verdict %s", state, el, word), m.Width-1))
}

// eventSpan is the wall time covered by the events stream.
func (m *Model) eventSpan() time.Duration {
	if len(m.Sum.Events) < 2 {
		return 0
	}
	first := m.Sum.Events[0].Ts
	last := m.Sum.Events[len(m.Sum.Events)-1].Ts
	if first <= 0 || last <= first {
		return 0
	}
	return time.Duration((last - first) * float64(time.Second))
}

func (m *Model) flowLine() string {
	reached := m.Sum.FlowReached()
	active := ""
	if m.Mode == ModeLive && !m.Done {
		active = m.activePhase()
	}
	parts := make([]string, 0, len(FlowNodes))
	for _, n := range FlowNodes {
		tag := "·"
		if reached[n] {
			tag = "✔"
		}
		if n == active && !reached[n] {
			tag = "◐" // heating
			if m.Anim {
				tag = []string{"◐", "◓", "◑", "◒"}[m.pulse%4] // subtle heat-pulse
			}
		}
		if n == "verdict" {
			switch m.Sum.Status {
			case "accepted", "rejected", "refused", "error":
				tag = "★"
			}
		}
		parts = append(parts, n+tag)
	}
	full := strings.Join(parts, " ─▶ ")
	if lipgloss.Width(full) <= m.Width-3 {
		return full
	}
	compact := strings.Join(parts, "→")
	if lipgloss.Width(compact) <= m.Width-3 {
		return compact
	}
	return fit(compact, m.Width-3)
}

func shortTarget(t string) string {
	if i := strings.LastIndex(t, "/"); i >= 0 {
		t = t[i+1:]
	}
	return t
}

func shortSHA(s string) string {
	if s == "" {
		return "—"
	}
	if len(s) > 8 {
		return s[:8] + "…"
	}
	return s
}

func (m *Model) resultsBox() string {
	return m.resultsBoxW(m.Width - 4)
}

func (m *Model) resultsBoxW(w int) string {
	s := m.Sum
	lines := []string{
		"target   " + shortTarget(s.Target),
		"provider " + s.Provider + " · model " + DisplayModel(s.Provider, s.Model),
		fmt.Sprintf("oracle   %d cases · sha %s", s.NCases, shortSHA(s.OracleSHA)),
		fmt.Sprintf("attempts %d", s.Attempts),
	}
	switch {
	case s.HasSpeedup && s.HasLB:
		lines = append(lines, fmt.Sprintf("speedup  %.2fx · lower bound %.2fx", s.Speedup, s.SpeedupLB))
	case s.HasSpeedup:
		lines = append(lines, fmt.Sprintf("speedup  %.2fx · lower bound —", s.Speedup))
	default:
		lines = append(lines, "speedup  — (no accepted candidate)")
	}
	body := strings.Join(fitLines(lines, w-4), "\n")
	style := borderNormal
	if m.Focus == 0 {
		style = borderFocused
	}
	return style.Render(body)
}

func (m *Model) verdictBox() string {
	if m.Mode == ModeLive && !m.Done {
		sub := "heating — " + m.activePhase()
		if m.WaitingModel {
			sub = "waiting for the model…"
		}
		return " " + colEmber.Render("VERDICT: RUNNING") + "\n" +
			" " + colDim.Render(fit(sub, m.Width-2))
	}
	word, sub := Verdict(m.Sum.Status)
	if m.Mode == ModeLive && m.KilledByUser {
		word, sub = "COLD", "stopped by user — run left in progress (resumable)"
	}
	st := colGold
	switch word {
	case "INGOT":
		st = colEmber
	case "SLAG":
		st = colSlag
	case "ASH", "COLD":
		st = colDim
	}
	out := " " + st.Render("VERDICT: "+word) + "\n" +
		" " + colDim.Render(fit(sub, m.Width-2))
	if m.CrashNote != "" {
		out += "\n " + colDim.Render(fit(m.CrashNote+" — see log", m.Width-2))
	} else {
		out += "\n " + colDim.Render(fit(strings.ReplaceAll(m.Sum.Reason, "\n", " "), m.Width-4))
	}
	return out
}

func (m *Model) logPane() string {
	style := borderNormal
	if m.Focus == 1 {
		style = borderFocused
	}
	content := m.LogVP.View()
	if len(m.LogLines) == 0 {
		content = " (no events yet)"
	}
	title := fmt.Sprintf(" log · %d lines", len(m.LogLines))
	if m.SkippedLines > 0 {
		title += fmt.Sprintf(" · %d skipped", m.SkippedLines)
	}
	return style.Render(fit(title, m.Width-4) + "\n" + content)
}
