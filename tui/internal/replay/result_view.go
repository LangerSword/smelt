package replay

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// resultTabs are the Result screen's tabs (keys 1-4, ←/→).
var resultTabs = []string{"summary", "rust", "compare", "diff"}

// ResultState is the Result screen: the run's final artifacts — read from
// runs/<id>/ only — on four tabs plus the attempts strip.
type ResultState struct {
	Data  *ResultData
	Tab   int
	VP    viewport.Model
	ready bool
}

// ResultOpen reports whether the Result screen is showing (the App uses this
// to route esc back one level instead of leaving the run screen).
func (m *Model) ResultOpen() bool { return m.ShowResult && m.Res != nil }

// openResult loads the run's artifacts and shows the Result screen. It is
// called by `r` and automatically when a live run ends accepted/rejected.
func (m *Model) openResult() {
	dir := m.resultDir()
	if dir == "" {
		m.ExtraLog = append(m.ExtraLog, "result: the run directory is not known yet — press r again in a moment")
		m.refreshLog()
		return
	}
	tab := 0
	if m.Res != nil {
		tab = m.Res.Tab
	}
	m.Res = &ResultState{Data: LoadResult(dir), Tab: tab}
	m.ShowResult = true
}

func (m *Model) closeResult() { m.ShowResult = false }

// resultDir is the run directory whose artifacts the Result screen reads.
func (m *Model) resultDir() string {
	if m.Mode == ModeLive && m.Live != nil {
		return m.Live.RunDir
	}
	return m.Sum.Dir
}

// updateResult handles keys on the Result screen.
func (m *Model) updateResult(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "q", "ctrl+c":
		if m.Mode == ModeLive && !m.Done && m.Live != nil {
			m.Live.Kill()
			m.KilledByUser = true
		}
		return m, tea.Quit
	case "esc", "r":
		m.closeResult()
		return m, nil
	case "1", "2", "3", "4":
		m.Res.Tab = int(msg.String()[0] - '1')
		return m, nil
	case "tab", "right", "l":
		m.Res.Tab = (m.Res.Tab + 1) % len(resultTabs)
		return m, nil
	case "left", "h":
		m.Res.Tab = (m.Res.Tab + len(resultTabs) - 1) % len(resultTabs)
		return m, nil
	case "pgup", "pgdown", "j", "k", "up", "down":
		if m.Res.ready {
			var cmd tea.Cmd
			m.Res.VP, cmd = m.Res.VP.Update(msg)
			return m, cmd
		}
	}
	return m, nil
}

// resultView renders the Result screen:
//
//	header · tab bar · tab content (scrollable, bordered) · attempts strip · keys
func (m *Model) resultView() string {
	strip := m.resultStrip()
	m.layoutResult(len(strip))
	var b strings.Builder
	b.WriteString(m.header() + "\n")
	b.WriteString(m.resultTabsLine() + "\n")
	title := fit(" "+resultTabs[m.Res.Tab], m.Res.VP.Width)
	body := m.Res.VP.View()
	if strings.TrimSpace(body) == "" {
		body = " (empty)"
	}
	b.WriteString(borderNormal.Render(title+"\n"+body) + "\n")
	for _, ln := range strip {
		b.WriteString(ln + "\n")
	}
	b.WriteString(colDim.Render(fit(" 1-4/←→ tabs · tab next · j/k ↑/↓ scroll · r/esc back · q quit", m.Width-1)))
	return b.String()
}

// layoutResult sizes the content viewport, accounting for the attempts strip.
func (m *Model) layoutResult(stripH int) {
	r := m.Res
	if stripH < 1 {
		stripH = 1
	}
	w := m.Width - 6
	if w < 10 {
		w = 10
	}
	h := m.Height - 6 - stripH
	if h < 3 {
		h = 3
	}
	if !r.ready {
		r.VP = viewport.New(w, h)
		r.ready = true
	} else {
		r.VP.Width, r.VP.Height = w, h
	}
	r.VP.SetContent(m.resultContent())
}

func (m *Model) resultTabsLine() string {
	parts := make([]string, 0, len(resultTabs))
	for i, name := range resultTabs {
		txt := fmt.Sprintf("%d %s", i+1, name)
		if i == m.Res.Tab {
			parts = append(parts, colEmber.Render("["+txt+"]"))
		} else {
			parts = append(parts, colDim.Render(" "+txt+" "))
		}
	}
	return " " + fit(strings.Join(parts, " "), m.Width-2)
}

func (m *Model) resultContent() string {
	switch m.Res.Tab {
	case 1:
		return m.rustTab()
	case 2:
		return m.compareTab()
	case 3:
		return m.diffTab()
	}
	return m.summaryTab()
}

// summaryTab — verdict, oracle cases, speedup with lower bound, attempts,
// model, time, target and run identity.
func (m *Model) summaryTab() string {
	d := m.Res.Data
	s := m.Sum
	w := m.Res.VP.Width
	status := d.Status
	if status == "" {
		status = s.Status
	}
	word, sub := Verdict(status)
	var lines []string
	add := func(k, v string) {
		v = strings.ReplaceAll(v, "\n", " ")
		lines = append(lines, fit(fmt.Sprintf("%-9s %s", k, v), w))
	}
	add("verdict", verdictGlyph(word)+" "+word+" — "+sub)
	reason := d.Reason
	if reason == "" {
		reason = s.Reason
	}
	if reason != "" {
		add("reason", reason)
	}
	ncases, sha := s.NCases, s.OracleSHA
	if ncases == 0 {
		ncases = d.NCases
	}
	if d.OracleSHA != "" {
		sha = d.OracleSHA
	}
	add("oracle", fmt.Sprintf("%d cases · sha %s", ncases, shortSHA(sha)))
	add("speedup", speedupSummary(s))
	add("attempts", attemptsLine(d))
	provider := s.Provider
	if provider == "" {
		provider = d.Provider
	}
	model := s.Model
	if model == "" {
		model = d.Model
	}
	add("model", provider+" · "+DisplayModel(provider, model))
	add("time", m.timeLine())
	target := s.Target
	if target == "" && d.TargetPath != "" {
		target = d.TargetPath + ":" + d.Qualname
	}
	add("target", shortTarget(target))
	add("run", runLine(d))
	return strings.Join(lines, "\n")
}

func speedupSummary(s *RunSummary) string {
	switch {
	case s.HasSpeedup && s.HasLB:
		return fmt.Sprintf("%.2fx measured · conservative lower bound %.2fx", s.Speedup, s.SpeedupLB)
	case s.HasSpeedup:
		return fmt.Sprintf("%.2fx measured · lower bound —", s.Speedup)
	default:
		return "— (no measured candidate)"
	}
}

func attemptsLine(d *ResultData) string {
	n := len(d.Attempts)
	if n == 0 {
		return "0 — nothing was generated"
	}
	acceptedAt := 0
	allNoGain := true
	for _, a := range d.Attempts {
		if a.Outcome == "ACCEPTED" {
			acceptedAt = a.N
		}
		if !strings.HasPrefix(a.Outcome, "reject_no_meaningful_gain") {
			allNoGain = false
		}
	}
	switch {
	case acceptedAt > 0:
		return fmt.Sprintf("%d — accepted on attempt %d", n, acceptedAt)
	case allNoGain:
		return fmt.Sprintf("%d — no meaningful gain (below the 1.5x threshold) — budget exhausted", n)
	default:
		return fmt.Sprintf("%d — last: %s", n, stripOutcome(d.Attempts[n-1]))
	}
}

func (m *Model) timeLine() string {
	d := m.eventSpan()
	if d < time.Second {
		return "—"
	}
	return d.Round(time.Second).String()
}

func runLine(d *ResultData) string {
	created := d.CreatedAt
	if i := strings.Index(created, "T"); i >= 0 && len(created) >= i+6 {
		created = created[:i] + " " + created[i+1:i+6]
	}
	parts := []string{}
	if d.RunID != "" {
		parts = append(parts, d.RunID)
	}
	if created != "" {
		parts = append(parts, created)
	}
	if d.Version != "" {
		parts = append(parts, "smelt "+d.Version)
	}
	return strings.Join(parts, " · ")
}

// rustTab — the final generated lib.rs with line numbers and simple syntax
// colouring. SLAG shows the last attempt marked "rejected candidate"; ASH
// (refused) shows the refusal reason and the refactor hint instead.
func (m *Model) rustTab() string {
	d := m.Res.Data
	w := m.Res.VP.Width
	var lines []string
	if d.Lib == "" {
		lines = append(lines, fit("candidate  "+libErrText(d), w))
		if d.Refusal != "" {
			lines = append(lines, "")
			lines = append(lines, fit("reason     "+d.Refusal, w))
			if d.RefusalHint != "" {
				lines = append(lines, fit("hint       "+d.RefusalHint, w))
			} else {
				lines = append(lines, fit("hint       — none recorded for this refusal", w))
			}
		}
		return strings.Join(lines, "\n")
	}
	title := fmt.Sprintf("attempt %d · accepted candidate", d.LibAttempt)
	if d.Status == "rejected" {
		title = fmt.Sprintf("attempt %d · rejected candidate — not applied", d.LibAttempt)
	}
	if d.LibNote != "" {
		title += " · " + d.LibNote
	}
	lines = append(lines, fit(title, w))
	lines = append(lines, "")
	code := strings.Split(strings.TrimRight(strings.ReplaceAll(d.Lib, "\r\n", "\n"), "\n"), "\n")
	for i, ln := range code {
		prefix := fmt.Sprintf("%4d │ ", i+1)
		body := fit(ln, w-lipgloss.Width(prefix))
		lines = append(lines, colDim.Render(prefix)+highlightRust(body))
	}
	return strings.Join(lines, "\n")
}

func libErrText(d *ResultData) string {
	if d.LibErr != "" {
		return d.LibErr
	}
	return "no lib.rs in this run dir"
}

// compareTab — the Python original next to the Rust candidate. Two columns
// when width ≥ 120, stacked otherwise; both sides scroll together (one
// viewport).
func (m *Model) compareTab() string {
	d := m.Res.Data
	w := m.Res.VP.Width
	pyLabel := "python original"
	if d.TargetPath != "" {
		pyLabel = "python · " + shortTarget(d.TargetPath)
		if d.Qualname != "" {
			pyLabel += ":" + d.Qualname
		}
	}
	rsLabel := "rust · no candidate"
	if d.Lib != "" {
		rsLabel = fmt.Sprintf("rust · attempts/it%d/lib.rs", d.LibAttempt)
	}
	var pyLines []string
	if d.PythonErr != "" {
		pyLines = []string{"(" + d.PythonErr + ")"}
	} else {
		pyLines = strings.Split(strings.TrimRight(strings.ReplaceAll(d.Python, "\r\n", "\n"), "\n"), "\n")
	}
	if d.PythonChanged {
		pyLines = append([]string{"(!) source changed since the run (sha256 mismatch) — read with care"}, pyLines...)
	}
	var rsLines []string
	if d.Lib != "" {
		rsLines = strings.Split(strings.TrimRight(strings.ReplaceAll(d.Lib, "\r\n", "\n"), "\n"), "\n")
	} else {
		rsLines = []string{"(" + libErrText(d) + ")"}
	}

	var out []string
	if m.Width >= 120 {
		colW := (w - 3) / 2
		out = append(out, fit(pyLabel, colW)+" │ "+fit(rsLabel, colW))
		n := len(pyLines)
		if len(rsLines) > n {
			n = len(rsLines)
		}
		for i := 0; i < n; i++ {
			l, r := "", ""
			if i < len(pyLines) {
				l = pyLines[i]
			}
			if i < len(rsLines) {
				r = rsLines[i]
			}
			out = append(out, fit(l, colW)+" │ "+fit(r, colW))
		}
		return strings.Join(out, "\n")
	}
	out = append(out, "── "+pyLabel+" ──")
	out = append(out, fitLines(pyLines, w)...)
	out = append(out, "", "── "+rsLabel+" ──")
	out = append(out, fitLines(rsLines, w)...)
	return strings.Join(out, "\n")
}

// diffTab — the view-only diff from `smelt apply` (new crate file + shim),
// with +/- colouring, the build command and the revert note.
func (m *Model) diffTab() string {
	d := m.Res.Data
	w := m.Res.VP.Width
	if len(d.Diff) == 0 {
		note := d.DiffNote
		if note == "" {
			note = "no diff available for this run"
		}
		return strings.Join([]string{
			fit(" "+note, w),
			"",
			fit(" view only — smelt apply never writes into your repo", w),
		}, "\n")
	}
	out := make([]string, 0, len(d.Diff))
	for _, ln := range d.Diff {
		out = append(out, colorizeDiffLine(fit(ln, w)))
	}
	return strings.Join(out, "\n")
}

// resultStrip is the attempts strip: one line per attempt (a mismatch with a
// recorded sample spells out input/expected/got) so the feedback loop —
// compile error → mismatch → no gain → accepted — stays visible.
const resultStripMaxLines = 9

func (m *Model) resultStrip() []string {
	d := m.Res.Data
	var entries [][]string
	switch {
	case d != nil && len(d.Attempts) > 0:
		for _, a := range d.Attempts {
			entries = append(entries, stripAttemptLines(a))
		}
	case d != nil && d.Status == "refused":
		entries = [][]string{{"— none · refused before generation"}}
	case d != nil && d.Status == "error":
		entries = [][]string{{"— none · stopped with an error"}}
	case d != nil && (d.Status == "" || d.Status == "in_progress"):
		entries = [][]string{{"— none yet · the run has not finished"}}
	default:
		entries = [][]string{{"— none (no attempt records in this run)"}}
	}
	var out []string
	for i, e := range entries {
		for j, ln := range e {
			if len(out) >= resultStripMaxLines {
				out = append(out, fmt.Sprintf("          … +%d more attempt(s)", len(entries)-i))
				return out
			}
			prefix := "            "
			if j == 0 {
				prefix = "          "
				if i == 0 {
					prefix = "attempts  "
				}
			}
			out = append(out, fit(prefix+ln, m.Width-1))
		}
	}
	return out
}

// stripAttemptLines renders one attempt: normally one line; a mismatch with a
// recorded sample also spells out the first failing input, expected and got.
func stripAttemptLines(a ResultAttempt) []string {
	head := fmt.Sprintf("%d %s", a.N, stripOutcome(a))
	s := a.Sample
	if s == nil || !strings.HasPrefix(a.Outcome, "verify_mismatch") {
		return []string{head}
	}
	lines := []string{head}
	var mid []string
	if len(s.Args) > 0 {
		mid = append(mid, "in ["+strings.Join(s.Args, " ")+"]")
	}
	if s.Want != "" {
		mid = append(mid, "want "+s.Want)
	}
	if len(mid) > 0 {
		lines = append(lines, strings.Join(mid, " · "))
	}
	if s.Got != "" {
		lines = append(lines, "got "+s.Got)
	}
	return lines
}

// stripOutcome renders one attempt's outcome for the strip.
func stripOutcome(a ResultAttempt) string {
	o := a.Outcome
	switch {
	case o == "ACCEPTED":
		if a.Bench != "" && a.Bench != "-" {
			return "◆ accepted · " + a.Bench
		}
		return "◆ accepted"
	case strings.HasPrefix(o, "reject_no_meaningful_gain"):
		tail := strings.TrimPrefix(o, "reject_no_meaningful_gain: ")
		if tail == o {
			tail = a.Bench
		}
		if tail == "" || tail == "-" {
			tail = "below the 1.5x threshold"
		}
		return "◇ no gain · " + tail
	case strings.HasPrefix(o, "verify_mismatch"):
		if a.Sample != nil {
			return "✗ mismatch · " + sampleHead(a.Sample)
		}
		tail := strings.TrimPrefix(o, "verify_mismatch: ")
		if tail == o || tail == "" {
			tail = a.Verify
		}
		return "✗ mismatch · " + tail
	case strings.HasPrefix(o, "build_error"):
		return "✗ " + buildErrKind(o)
	case strings.HasPrefix(o, "safety_violation"):
		tail := strings.TrimPrefix(o, "safety_violation: ")
		tail = strings.TrimPrefix(tail, "safety scan failed: ")
		if tail == "" {
			return "✗ safety violation"
		}
		return "✗ safety violation · " + tail
	case strings.HasPrefix(o, "bench_insufficient"):
		return "✗ bench failed · insufficient data"
	case o == "":
		return "· no outcome recorded"
	default:
		return o
	}
}

func buildErrKind(o string) string {
	inner := ""
	if i := strings.Index(o, "["); i >= 0 {
		if j := strings.Index(o[i:], "]"); j > 0 {
			inner = o[i+1 : i+j]
		}
	}
	switch inner {
	case "compile_error":
		return "compile error"
	case "api_drift":
		return "build error · api drift"
	case "network":
		return "build error · network"
	case "missing_artifact":
		return "build error · missing artifact"
	case "":
		return "build error"
	default:
		return "build error · " + inner
	}
}

// sampleHead renders the case id and reason of a failing oracle case.
func sampleHead(s *MismatchSample) string {
	if s.CaseID == "" {
		return s.Why
	}
	if s.Why == "" {
		return s.CaseID
	}
	return s.CaseID + ": " + s.Why
}

// verdictGlyph maps a verdict word to its glyph (words are always shown too).
func verdictGlyph(word string) string {
	switch word {
	case "INGOT":
		return "◆"
	case "SLAG":
		return "◇"
	case "ASH":
		return "△"
	case "COLD":
		return "○"
	}
	return "·"
}

// colorizeDiffLine tints a view-only diff line (+ ember, - slag, headers).
func colorizeDiffLine(ln string) string {
	switch {
	case strings.HasPrefix(ln, "+"):
		return colEmber.Render(ln)
	case strings.HasPrefix(ln, "-"):
		return colSlag.Render(ln)
	case strings.HasPrefix(ln, "## "):
		return colGold.Render(ln)
	case strings.HasPrefix(ln, "#"):
		return colDim.Render(ln)
	case strings.HasPrefix(ln, "```"):
		return colDim.Render(ln)
	}
	return ln
}

// rustKeywords is the (simple) keyword set for the RUST tab colouring.
var rustKeywords = map[string]bool{
	"fn": true, "let": true, "mut": true, "pub": true, "use": true,
	"mod": true, "impl": true, "for": true, "in": true, "while": true,
	"loop": true, "if": true, "else": true, "match": true, "return": true,
	"struct": true, "enum": true, "trait": true, "where": true, "as": true,
	"dyn": true, "ref": true, "self": true, "Self": true, "crate": true,
	"super": true, "const": true, "static": true, "move": true, "unsafe": true,
	"async": true, "await": true, "type": true, "true": true, "false": true,
	"usize": true, "isize": true, "i8": true, "i16": true, "i32": true,
	"i64": true, "i128": true, "u8": true, "u16": true, "u32": true,
	"u64": true, "u128": true, "f32": true, "f64": true, "bool": true,
	"char": true, "str": true,
}

func isIdentStart(b byte) bool {
	return b == '_' || b >= 'a' && b <= 'z' || b >= 'A' && b <= 'Z'
}

func isIdentChar(b byte) bool {
	return isIdentStart(b) || b >= '0' && b <= '9'
}

// highlightRust applies simple syntax colouring to one line of Rust:
// comments dim, strings gold, keywords ember, macros gold. Colour never
// carries meaning — the words are all there.
func highlightRust(line string) string {
	var b strings.Builder
	n := len(line)
	for i := 0; i < n; {
		c := line[i]
		switch {
		case c == '/' && i+1 < n && line[i+1] == '/':
			b.WriteString(colDim.Render(line[i:]))
			i = n
		case c == '"':
			j := i + 1
			for j < n {
				if line[j] == '\\' {
					j += 2
					continue
				}
				if line[j] == '"' {
					j++
					break
				}
				j++
			}
			if j > n {
				j = n
			}
			b.WriteString(colGold.Render(line[i:j]))
			i = j
		case isIdentStart(c):
			j := i
			for j < n && isIdentChar(line[j]) {
				j++
			}
			word := line[i:j]
			switch {
			case j < n && line[j] == '!':
				b.WriteString(colGold.Render(word + "!"))
				i = j + 1
			case rustKeywords[word]:
				b.WriteString(colEmber.Render(word))
				i = j
			default:
				b.WriteString(word)
				i = j
			}
		default:
			b.WriteByte(c)
			i++
		}
	}
	return b.String()
}
