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

func (m *Model) View() string {
	if !m.ready {
		m.layout()
	}
	var b strings.Builder
	b.WriteString(m.header() + "\n")
	b.WriteString(" " + m.flowLine() + "\n")
	if m.Mode == ModeLive {
		b.WriteString(" " + m.liveStatus() + "\n")
	}
	b.WriteString(m.resultsBox() + "\n")
	b.WriteString(m.verdictBox() + "\n")
	b.WriteString(m.logPane() + "\n")
	b.WriteString(colDim.Render(fit(" q quit · tab panes · ↑/↓ scroll · schema v1", m.Width-1)))
	return b.String()
}

func (m *Model) header() string {
	left := "FURNACE · replay · " + m.Sum.RunID
	if m.Mode == ModeLive {
		left = "FURNACE · run · " + m.liveRunID()
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

func (m *Model) liveRunID() string {
	if m.Live == nil || m.Live.RunDir == "" {
		return "…"
	}
	if i := strings.LastIndex(m.Live.RunDir, "/"); i >= 0 {
		return m.Live.RunDir[i+1:]
	}
	return m.Live.RunDir
}

func (m *Model) liveStatus() string {
	elapsed := time.Since(m.Started).Round(time.Second)
	if elapsed < 0 {
		elapsed = 0
	}
	state := "heating · " + m.activePhase()
	if m.WaitingModel {
		state = "waiting for the model…"
	}
	if m.Done {
		if m.KilledByUser {
			state = "stopped by user"
		} else {
			state = "finished · " + m.Sum.Status
		}
	}
	line := fmt.Sprintf("run %s · %s · %s", m.liveRunID(), elapsed, state)
	return fit(line, m.Width-3)
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
	body := strings.Join(fitLines(lines, m.Width-4), "\n")
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
