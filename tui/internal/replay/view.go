package replay

import (
	"fmt"
	"strings"

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
	b.WriteString(m.resultsBox() + "\n")
	b.WriteString(m.verdictBox() + "\n")
	b.WriteString(m.logPane() + "\n")
	b.WriteString(colDim.Render(fit(" q quit · tab panes · ↑/↓ scroll · schema v1", m.Width-1)))
	return b.String()
}

func (m *Model) header() string {
	right := fit(m.Sum.Provider+" · "+DisplayModel(m.Sum.Provider, m.Sum.Model), m.Width/2)
	left := fit("FURNACE · replay · "+m.Sum.RunID, m.Width-lipgloss.Width(right)-3)
	if left == "" {
		return " " + right
	}
	pad := m.Width - 2 - lipgloss.Width(left) - lipgloss.Width(right)
	if pad < 1 {
		pad = 1
	}
	return " " + left + strings.Repeat(" ", pad) + right
}

func (m *Model) flowLine() string {
	reached := m.Sum.FlowReached()
	parts := make([]string, 0, len(FlowNodes))
	for _, n := range FlowNodes {
		tag := "·"
		if reached[n] {
			tag = "✔"
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
	word, sub := Verdict(m.Sum.Status)
	st := colGold
	switch word {
	case "INGOT":
		st = colEmber
	case "SLAG":
		st = colSlag
	case "ASH":
		st = colDim
	}
	reason := fit(strings.ReplaceAll(m.Sum.Reason, "\n", " "), m.Width-4)
	return " " + st.Render("VERDICT: "+word) + "\n" +
		" " + colDim.Render(fit(sub, m.Width-2)) + "\n" +
		" " + colDim.Render(reason)
}

func (m *Model) logPane() string {
	style := borderNormal
	if m.Focus == 1 {
		style = borderFocused
	}
	content := m.LogVP.View()
	if len(m.Sum.Log) == 0 {
		content = " (no events)"
	} else {
		content = m.LogVP.View()
	}
	title := fit(fmt.Sprintf(" log · %d lines", len(m.Sum.Log)), m.Width-4)
	return style.Render(title + "\n" + content)
}
