package replay

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Screen selects which view the App renders.
type Screen int

const (
	ScreenHome Screen = iota
	ScreenRun
	ScreenText
)

type scanItem struct {
	File     string `json:"file"`
	Function string `json:"function"`
	Status   string `json:"status"`
	Reason   string `json:"reason"`
	Tier     string `json:"tier"`
	Param    string `json:"param"`
}

type scanResult struct {
	Summary struct {
		Root string `json:"root"`
	} `json:"summary"`
	Candidates []scanItem `json:"candidates"`
}

type doctorCheck struct {
	Name   string `json:"name"`
	OK     bool   `json:"ok"`
	Detail string `json:"detail"`
}

type doctorResult struct {
	Checks []doctorCheck `json:"checks"`
	Fails  int           `json:"fails"`
	Warns  int           `json:"warns"`
}

type smeltResultMsg struct {
	kind  string
	arg   string
	out   string
	err   error
	_live *LiveRun
}

const helpText = `furnace home — commands

  /scan <path>              list candidate functions (with skip reasons)
  /run <file.py:fn> [--provider p] [--model m]
                            start a live run
  <file.py:fn>              same as /run with the current provider/model
  /resume <run-dir>         open a finished (or interrupted) run
  /report <run-dir>         show the run's markdown report
  /provider [name] [model]  picker when bare; sets directly with args
  /model                    choose the model (picker)
  /sessions  (ctrl+r)       run history picker — verdict · speedup · target
  /diff                     view-only diff for the open run (smelt apply)
  /doctor                   environment + provider checks (smelt doctor --json)
  /clear                    clear the candidate list
  /help                     this text
  /quit                     leave furnace

home keys:  tab complete/focus · ↑/↓ choose · enter run/open · esc cancel
            ? help · ctrl+r sessions · ctrl+c quit
run view:   esc back · r result · d diff (view only) · j/k ↑/↓ scroll · q quit
            ctrl+c once stops the run (confirm), twice quits
result:     1-4/←→ tabs · tab next · j/k ↑/↓ scroll · esc/r back · q quit`

type cmdSpec struct{ name, desc string }

var commandSpecs = []cmdSpec{
	{"/scan", "list candidate functions (with skip reasons)"},
	{"/run", "start a live run: /run file.py:fn [--provider p] [--model m]"},
	{"/resume", "open a finished or interrupted run"},
	{"/report", "show a run's markdown report"},
	{"/provider", "choose a provider (picker)"},
	{"/model", "choose a model (picker)"},
	{"/sessions", "run history picker (ctrl+r)"},
	{"/diff", "view-only diff for the open run"},
	{"/doctor", "environment + provider checks"},
	{"/clear", "clear the candidate list"},
	{"/help", "keybindings and commands"},
	{"/quit", "leave furnace"},
}

type pickerState struct {
	kind  string // provider | model | sessions
	items []string
	notes []string
	sel   int
}

// App is the T3 home screen: prompt box, scan picker, history, and the
// run/text screens it delegates to.
type App struct {
	Width, Height int
	Screen        Screen
	SmeltBin      string
	RunsDir       string
	Provider      string
	Model         string
	Anim          bool

	Input      textinput.Model
	Focus      int // 0 input, 1 candidates, 2 history
	Cands      []scanItem
	CandSel    int
	ScanRoot   string
	History    []string
	HistSel    int
	Status     string
	Prompts    []string // submitted prompt history (↑/↓)
	PromptIdx  int
	MenuSel    int
	menuHidden bool
	Picker     *pickerState
	lastCtrlC  time.Time

	Run       *Model
	TextTitle string
	Text      string
	textVP    viewport.Model

	ready bool
}

// NewApp builds the home screen.
func NewApp(smeltBin, runsDir string) *App {
	ti := textinput.New()
	ti.Placeholder = "type a command (/scan, /run, /help) or a target file.py:fn"
	ti.Prompt = "❯ "
	ti.Focus()
	a := &App{SmeltBin: smeltBin, RunsDir: runsDir, Provider: "gemini",
		Input: ti, Width: 100, Height: 30}
	a.loadHistory()
	return a
}

func (a *App) loadHistory() {
	a.History = nil
	entries, err := os.ReadDir(a.RunsDir)
	if err != nil {
		return
	}
	for _, e := range entries {
		if e.IsDir() {
			a.History = append(a.History, filepath.Join(a.RunsDir, e.Name()))
		}
	}
	sort.Sort(sort.Reverse(sort.StringSlice(a.History)))
	if len(a.History) > 12 {
		a.History = a.History[:12]
	}
}

func (a *App) modelDisplay() string {
	if a.Model == "" {
		return "(provider default)"
	}
	return a.Model
}

// menuMatches filters the slash-command list by the current input.
func (a *App) menuMatches() []cmdSpec {
	v := strings.TrimSpace(a.Input.Value())
	if !strings.HasPrefix(v, "/") || strings.Contains(v, " ") {
		return nil
	}
	var out []cmdSpec
	for _, c := range commandSpecs {
		if strings.HasPrefix(c.name, v) {
			out = append(out, c)
		}
	}
	return out
}

// promptBack / promptForward walk the submitted-prompt history (↑/↓).
func (a *App) promptBack() {
	if len(a.Prompts) == 0 {
		return
	}
	if a.PromptIdx > 0 {
		a.PromptIdx--
	}
	a.Input.SetValue(a.Prompts[a.PromptIdx])
	a.Input.CursorEnd()
}

func (a *App) promptForward() {
	if len(a.Prompts) == 0 {
		return
	}
	if a.PromptIdx < len(a.Prompts)-1 {
		a.PromptIdx++
		a.Input.SetValue(a.Prompts[a.PromptIdx])
	} else {
		a.PromptIdx = len(a.Prompts)
		a.Input.SetValue("")
	}
	a.Input.CursorEnd()
}

func (a *App) openPicker(kind string, items []string, current string) {
	p := &pickerState{kind: kind, items: items}
	for _, it := range items {
		note := ""
		if it == current {
			note = "current"
		}
		p.notes = append(p.notes, note)
	}
	a.Picker = p
}

func (a *App) openSessionsPicker() {
	p := &pickerState{kind: "sessions"}
	for _, dir := range a.History {
		note := "unreadable"
		if sum, err := LoadRun(dir); err == nil {
			word, _ := Verdict(sum.Status)
			note = word
			if sum.HasSpeedup {
				note += fmt.Sprintf(" · %.2fx", sum.Speedup)
			}
			if sum.Target != "" {
				note += " · " + shortTarget(sum.Target)
			}
		}
		p.items = append(p.items, filepath.Base(dir))
		p.notes = append(p.notes, note)
	}
	a.Picker = p
}

func (a *App) pickerEnter() (tea.Model, tea.Cmd) {
	p := a.Picker
	if p == nil || len(p.items) == 0 {
		a.Picker = nil
		return a, nil
	}
	sel := p.items[p.sel]
	a.Picker = nil
	switch p.kind {
	case "provider":
		a.Provider = sel
		a.Status = "provider set: " + a.Provider
	case "model":
		if sel == "(provider default)" {
			a.Model = ""
		} else {
			a.Model = sel
		}
		a.Status = "model set: " + a.modelDisplay()
	case "sessions":
		return a, a.openRun(filepath.Join(a.RunsDir, sel))
	}
	return a, nil
}

func (a *App) pickerView() string {
	p := a.Picker
	title := map[string]string{"provider": "choose provider", "model": "choose model", "sessions": "run history"}[p.kind]
	lines := []string{title}
	if len(p.items) == 0 {
		lines = append(lines, "  (nothing to choose)")
	}
	for i, it := range p.items {
		mark := "  "
		if i == p.sel {
			mark = "▸ "
		}
		note := ""
		if i < len(p.notes) && p.notes[i] != "" {
			note = "  — " + p.notes[i]
		}
		lines = append(lines, fit(mark+it+note, a.Width-10))
	}
	lines = append(lines, "", " enter select · esc cancel")
	return borderFocused.Render(strings.Join(lines, "\n"))
}

// colorizeDiff gives added lines the ember tint (view-only diffs, U4).
func colorizeDiff(s string) string {
	var out []string
	for _, ln := range strings.Split(s, "\n") {
		switch {
		case strings.HasPrefix(ln, "+"):
			out = append(out, colEmber.Render(ln))
		case strings.HasPrefix(ln, "-"):
			out = append(out, colSlag.Render(ln))
		default:
			out = append(out, ln)
		}
	}
	return strings.Join(out, "\n")
}

func (a *App) Init() tea.Cmd { return textinput.Blink }

func (a *App) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		a.Width, a.Height = msg.Width, msg.Height
		if a.Run != nil {
			a.Run.Update(tea.WindowSizeMsg{Width: msg.Width, Height: msg.Height - 1})
		}
		a.layoutText()
		return a, nil
	case tickMsg:
		if a.Screen == ScreenRun && a.Run != nil {
			rm, cmd := a.Run.Update(msg)
			a.Run = rm.(*Model)
			return a, cmd
		}
		return a, nil
	case smeltResultMsg:
		return a, a.handleSmeltResult(msg)
	case tea.KeyMsg:
		return a.handleKey(msg)
	}
	return a, nil
}

func (a *App) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch a.Screen {
	case ScreenRun:
		if a.Run == nil {
			a.Screen = ScreenHome
			return a, nil
		}
		switch msg.String() {
		case "?":
			a.showText("help", helpText)
			return a, nil
		case "esc":
			if a.Run != nil && a.Run.ResultOpen() {
				rm, cmd := a.Run.Update(msg) // esc closes the result first
				a.Run = rm.(*Model)
				return a, cmd
			}
			a.stopLiveIfRunning()
			a.Screen = ScreenHome
			a.loadHistory()
			a.Focus = 0
			a.Input.Focus()
			return a, nil
		case "d":
			if a.Run.Mode == ModeReplay || a.Run.Done {
				return a, a.runApply(a.runDir())
			}
			return a, nil
		case "q":
			a.stopLiveIfRunning()
			return a, tea.Quit
		case "ctrl+c":
			running := a.Run != nil && a.Run.Mode == ModeLive && !a.Run.Done
			if running {
				if time.Since(a.lastCtrlC) < 3*time.Second {
					a.stopLiveIfRunning()
					return a, tea.Quit
				}
				a.lastCtrlC = time.Now()
				a.stopLiveIfRunning()
				a.Status = "stopped — ctrl+c again to quit (the run is resumable)"
				return a, nil
			}
			if time.Since(a.lastCtrlC) < 3*time.Second {
				return a, tea.Quit
			}
			a.lastCtrlC = time.Now()
			a.Status = "press ctrl+c again to quit"
			return a, nil
		}
		rm, cmd := a.Run.Update(msg)
		a.Run = rm.(*Model)
		return a, cmd
	case ScreenText:
		switch msg.String() {
		case "esc", "q":
			a.Screen = ScreenHome
			a.Focus = 0
			a.Input.Focus()
			return a, nil
		}
		var cmd tea.Cmd
		a.textVP, cmd = a.textVP.Update(msg)
		return a, cmd
	case ScreenHome:
		if a.Picker != nil {
			switch msg.String() {
			case "esc", "q":
				a.Picker = nil
			case "up", "k":
				if a.Picker.sel > 0 {
					a.Picker.sel--
				}
			case "down", "j":
				if a.Picker.sel < len(a.Picker.items)-1 {
					a.Picker.sel++
				}
			case "enter":
				return a.pickerEnter()
			}
			return a, nil
		}
		switch msg.String() {
		case "ctrl+c":
			return a, tea.Quit
		case "ctrl+r":
			a.openSessionsPicker()
			return a, nil
		case "tab":
			if a.Focus == 0 {
				if m := a.menuMatches(); len(m) > 0 {
					a.Input.SetValue(m[a.MenuSel%len(m)].name + " ")
					a.MenuSel = 0
					return a, nil
				}
			}
			a.Focus = (a.Focus + 1) % 3
			if a.Focus == 0 {
				a.Input.Focus()
			} else {
				a.Input.Blur()
			}
			return a, nil
		case "?":
			a.showText("help", helpText)
			return a, nil
		case "enter":
			return a.homeEnter()
		case "esc":
			a.menuHidden = true
			return a, nil
		case "up":
			if a.Focus == 0 && len(a.menuMatches()) > 0 {
				if a.MenuSel > 0 {
					a.MenuSel--
				}
				return a, nil
			}
			if a.Focus == 0 {
				a.promptBack()
				return a, nil
			}
			if a.Focus == 1 && a.CandSel > 0 {
				a.CandSel--
			} else if a.Focus == 2 && a.HistSel > 0 {
				a.HistSel--
			}
			return a, nil
		case "down":
			if a.Focus == 0 && len(a.menuMatches()) > 0 {
				if a.MenuSel < len(a.menuMatches())-1 {
					a.MenuSel++
				}
				return a, nil
			}
			if a.Focus == 0 {
				a.promptForward()
				return a, nil
			}
			if a.Focus == 1 && a.CandSel < len(a.Cands)-1 {
				a.CandSel++
			} else if a.Focus == 2 && a.HistSel < len(a.History)-1 {
				a.HistSel++
			}
			return a, nil
		case "k":
			if a.Focus == 1 && a.CandSel > 0 {
				a.CandSel--
			} else if a.Focus == 2 && a.HistSel > 0 {
				a.HistSel--
			}
			return a, nil
		case "j":
			if a.Focus == 1 && a.CandSel < len(a.Cands)-1 {
				a.CandSel++
			} else if a.Focus == 2 && a.HistSel < len(a.History)-1 {
				a.HistSel++
			}
			return a, nil
		}
		if a.Focus == 0 {
			a.menuHidden = false
			var cmd tea.Cmd
			a.Input, cmd = a.Input.Update(msg)
			return a, cmd
		}
		return a, nil
	}
	return a, nil
}

func (a *App) homeEnter() (tea.Model, tea.Cmd) {
	switch a.Focus {
	case 0:
		line := strings.TrimSpace(a.Input.Value())
		a.Input.SetValue("")
		if line != "" {
			a.Prompts = append(a.Prompts, line)
			if len(a.Prompts) > 50 {
				a.Prompts = a.Prompts[1:]
			}
			a.PromptIdx = len(a.Prompts)
		}
		return a, a.execute(line)
	case 1:
		if len(a.Cands) == 0 {
			return a, nil
		}
		sel := a.Cands[a.CandSel]
		if sel.Status != "candidate" {
			a.Status = "skipped: " + sel.Reason
			return a, nil
		}
		target := sel.File + ":" + sel.Function
		if a.ScanRoot != "" {
			target = filepath.Join(a.ScanRoot, sel.File) + ":" + sel.Function
		}
		return a, a.startRun(target, a.Provider, a.Model)
	case 2:
		if len(a.History) == 0 {
			return a, nil
		}
		return a, a.openRun(a.History[a.HistSel])
	}
	return a, nil
}

func (a *App) execute(line string) tea.Cmd {
	a.Status = ""
	if line == "" {
		return nil
	}
	if !strings.HasPrefix(line, "/") {
		return a.startRun(line, a.Provider, a.Model)
	}
	parts := strings.Fields(line)
	switch parts[0] {
	case "/quit", "/q":
		return tea.Quit
	case "/help":
		a.showText("help", helpText)
		return nil
	case "/scan":
		if len(parts) < 2 {
			a.Status = "usage: /scan <path>"
			return nil
		}
		return a.runSmeltCmd("scan", parts[1], "scan", parts[1], "--json")
	case "/run":
		if len(parts) < 2 {
			a.Status = "usage: /run <file.py:fn> [--provider p] [--model m]"
			return nil
		}
		provider, model := a.Provider, a.Model
		for i := 2; i < len(parts); i++ {
			switch parts[i] {
			case "--provider":
				if i+1 < len(parts) {
					i++
					provider = parts[i]
				}
			case "--model":
				if i+1 < len(parts) {
					i++
					model = parts[i]
				}
			}
		}
		return a.startRun(parts[1], provider, model)
	case "/resume":
		if len(parts) < 2 {
			a.Status = "usage: /resume <run-dir>"
			return nil
		}
		return a.openRun(parts[1])
	case "/report":
		if len(parts) < 2 {
			a.Status = "usage: /report <run-dir>"
			return nil
		}
		path := filepath.Join(parts[1], "report.md")
		b, err := os.ReadFile(path)
		if err != nil {
			a.Status = "no report at " + path
			return nil
		}
		a.showText("report · "+parts[1], string(b))
		return nil
	case "/doctor":
		return a.runSmeltCmd("doctor", "", "doctor")
	case "/provider":
		if len(parts) >= 2 {
			a.Provider = parts[1]
			if len(parts) >= 3 {
				a.Model = parts[2]
			}
			a.Status = "provider set: " + a.Provider + " · model " + a.modelDisplay()
			return nil
		}
		a.openPicker("provider", []string{"gemini", "local", "do", "openai", "file", "fake"}, a.Provider)
		return nil
	case "/model":
		a.openPicker("model",
			[]string{"gemma-4-26b-a4b-it", "gemma-4-31b-it", "(provider default)"},
			a.modelDisplay())
		return nil
	case "/sessions":
		a.openSessionsPicker()
		return nil
	case "/diff":
		if a.Run != nil {
			return a.runApply(a.runDir())
		}
		a.Status = "no run open — /sessions or /resume <dir> first"
		return nil
	case "/clear":
		a.Cands = nil
		a.Status = "cleared"
		return nil
	default:
		a.Status = "unknown command: " + parts[0] + " (try /help)"
		return nil
	}
}

func (a *App) startRun(target, provider, model string) tea.Cmd {
	bin, runs := a.SmeltBin, a.RunsDir
	a.Status = "starting: " + target
	return func() tea.Msg {
		live, err := StartLive(bin, target, provider, model, runs)
		if err != nil {
			return smeltResultMsg{kind: "starterr", arg: target, err: err}
		}
		return smeltResultMsg{kind: "started", arg: target, _live: live}
	}
}

func (a *App) openRun(dir string) tea.Cmd {
	sum, err := LoadRun(dir)
	if err != nil {
		a.Status = fmt.Sprintf("cannot open %s: %v", dir, err)
		return nil
	}
	a.Run = New(sum)
	a.Run.Anim = a.Anim
	a.Screen = ScreenRun
	a.Run.Update(tea.WindowSizeMsg{Width: a.Width, Height: a.Height - 1})
	return nil
}

func (a *App) runApply(dir string) tea.Cmd {
	return a.runSmeltCmd("apply", dir, "apply", dir)
}

func (a *App) runSmeltCmd(kind, arg string, smeltArgs ...string) tea.Cmd {
	bin := a.SmeltBin
	return func() tea.Msg {
		out, err := execSmelt(bin, smeltArgs...)
		return smeltResultMsg{kind: kind, arg: arg, out: out, err: err}
	}
}

func execSmelt(bin string, args ...string) (string, error) {
	cmd := exec.Command(bin, args...)
	out, err := cmd.CombinedOutput()
	return string(out), err
}

func (a *App) handleSmeltResult(msg smeltResultMsg) tea.Cmd {
	switch msg.kind {
	case "scan":
		if msg.err != nil {
			a.Status = "scan failed: " + msg.err.Error()
			return nil
		}
		var res scanResult
		if err := json.Unmarshal([]byte(msg.out), &res); err != nil {
			a.Status = "scan output unparsable: " + err.Error()
			return nil
		}
		a.Cands = res.Candidates
		a.ScanRoot = res.Summary.Root
		a.CandSel = 0
		n := 0
		for _, c := range a.Cands {
			if c.Status == "candidate" {
				n++
			}
		}
		a.Status = fmt.Sprintf("scan: %d candidate(s), %d skipped", n, len(a.Cands)-n)
		a.Focus = 1
		a.Input.Blur()
		return nil
	case "doctor":
		if msg.err != nil && msg.out == "" {
			a.Status = "doctor failed: " + msg.err.Error()
			return nil
		}
		var res doctorResult
		if err := json.Unmarshal([]byte(msg.out), &res); err != nil {
			a.showText("doctor (raw)", msg.out)
			return nil
		}
		var b strings.Builder
		b.WriteString("smelt doctor\n\n")
		for _, c := range res.Checks {
			mark := "✓"
			if !c.OK {
				mark = "✗"
			}
			b.WriteString(fmt.Sprintf("  %s %-22s %s\n", mark, c.Name, c.Detail))
		}
		b.WriteString(fmt.Sprintf("\nfails %d · warns %d\n", res.Fails, res.Warns))
		a.showText("doctor", b.String())
		return nil
	case "apply":
		if msg.err != nil && msg.out == "" {
			a.Status = "apply failed: " + msg.err.Error()
			return nil
		}
		a.showText("apply (view only) · "+msg.arg, colorizeDiff(msg.out))
		return nil
	case "started":
		if msg._live == nil {
			return nil
		}
		sum := &RunSummary{Dir: a.RunsDir, Status: "in_progress", Target: msg.arg,
			Provider: a.Provider, Model: a.Model}
		a.Run = NewLive(sum, msg._live)
		a.Run.Anim = a.Anim
		a.Screen = ScreenRun
		a.Run.Update(tea.WindowSizeMsg{Width: a.Width, Height: a.Height - 1})
		a.Status = "running: " + msg.arg
		return a.Run.Init() // start the live tick loop
	case "starterr":
		a.Status = "could not start smelt: " + msg.err.Error()
	}
	return nil
}

func (a *App) showText(title, text string) {
	a.TextTitle = title
	a.Text = text
	a.Screen = ScreenText
	a.layoutText()
}

func (a *App) layoutText() {
	h := a.Height - 3
	if h < 3 {
		h = 3
	}
	w := a.Width - 4
	if w < 10 {
		w = 10
	}
	if !a.ready {
		a.textVP = viewport.New(w, h)
		a.ready = true
	} else {
		a.textVP.Width = w
		a.textVP.Height = h
	}
	a.textVP.SetContent(a.Text)
}

func (a *App) stopLiveIfRunning() {
	if a.Run != nil && a.Run.Mode == ModeLive && !a.Run.Done && a.Run.Live != nil {
		a.Run.Live.Kill()
		a.Run.KilledByUser = true
	}
}

func (a *App) runDir() string {
	if a.Run == nil {
		return a.RunsDir
	}
	if a.Run.Mode == ModeLive {
		return a.Run.RunDirForReport(a.RunsDir)
	}
	return a.Run.Sum.Dir
}

func (a *App) View() string {
	switch a.Screen {
	case ScreenRun:
		if a.Run == nil {
			break
		}
		foot := colDim.Render(fit(" esc back · r result · d diff (view only) · j/k scroll · ctrl+c once stops, twice quits · q quit", a.Width-1))
		if a.Run.ResultOpen() {
			foot = colDim.Render(fit(" 1-4/←→ tabs · tab next · j/k ↑/↓ scroll · esc/r back · q quit", a.Width-1))
		}
		if a.Status != "" {
			foot = colDim.Render(fit(" "+a.Status, a.Width-1)) + "\n" + foot
		}
		return a.Run.View() + "\n" + foot
	case ScreenText:
		head := " " + fit("FURNACE · "+a.TextTitle, a.Width-2)
		foot := colDim.Render(fit(" esc back · ↑/↓ scroll", a.Width-1))
		return head + "\n" + a.textVP.View() + "\n" + foot
	}
	return a.homeView()
}

// banner is the small home-screen crest (≤6 lines, colour never carries meaning).
func banner() string {
	return colDim.Render(strings.Join([]string{
		"     (",
		"    ) (    FURNACE — smelt a slow Python function",
		"   (   )   into verified Rust. Only proven metal ships.",
		"    ) (",
		"     (",
	}, "\n"))
}

func (a *App) homeView() string {
	var b strings.Builder
	right := fit(a.Provider+" · "+a.modelDisplay(), a.Width/3)
	left := fit("FURNACE v"+Version+" · smelt home", a.Width-lipgloss.Width(right)-3)
	pad := a.Width - 2 - lipgloss.Width(left) - lipgloss.Width(right)
	if pad < 1 {
		pad = 1
	}
	b.WriteString(" " + left + strings.Repeat(" ", pad) + right + "\n")
	if a.Height >= 30 {
		b.WriteString(banner() + "\n")
	}
	if a.Picker != nil {
		b.WriteString(a.pickerView() + "\n")
		b.WriteString(a.Input.View() + "\n")
		b.WriteString(colDim.Render(fit(" picker: ↑/↓ choose · enter select · esc cancel", a.Width-1)))
		return b.String()
	}
	if len(a.Cands) == 0 && len(a.History) == 0 {
		b.WriteString(colDim.Render(fit(" welcome — try /scan . (list candidates) or /run file.py:fn", a.Width-1)) + "\n")
	}

	// two side-by-side boxes: candidates | recent runs
	boxW := a.Width/2 - 2
	if boxW < 20 {
		boxW = 20
	}
	candLines := []string{"candidates"}
	for i, c := range a.Cands {
		mark := "·"
		if c.Status == "candidate" {
			mark = "✔"
		}
		line := fmt.Sprintf("%s %s:%s", mark, c.File, c.Function)
		if i == a.CandSel && a.Focus == 1 {
			line = "▸ " + line
		} else {
			line = "  " + line
		}
		candLines = append(candLines, fit(line, boxW-2))
		if c.Status != "candidate" {
			candLines = append(candLines, fit("    — "+c.Reason, boxW-2))
		}
	}
	if len(a.Cands) == 0 {
		candLines = append(candLines, "  (run /scan <path>)")
	}
	histLines := []string{"recent runs"}
	for i, h := range a.History {
		name := filepath.Base(h)
		line := "  " + name
		if i == a.HistSel && a.Focus == 2 {
			line = "▸ " + name
		}
		histLines = append(histLines, fit(line, boxW-2))
	}
	if len(a.History) == 0 {
		histLines = append(histLines, "  (none yet)")
	}
	maxLines := a.Height - 13
	if maxLines < 3 {
		maxLines = 3
	}
	if len(candLines) > maxLines {
		candLines = candLines[:maxLines]
	}
	if len(histLines) > maxLines {
		histLines = histLines[:maxLines]
	}
	candBox := borderNormal.Render(strings.Join(candLines, "\n"))
	histBox := borderNormal.Render(strings.Join(histLines, "\n"))
	b.WriteString(lipgloss.JoinHorizontal(lipgloss.Top, candBox, " ", histBox) + "\n")
	if m := a.menuMatches(); len(m) > 0 && !a.menuHidden {
		if len(m) > 6 {
			m = m[:6]
		}
		for i, c := range m {
			mark := "  "
			if i == a.MenuSel%len(m) {
				mark = "▸ "
			}
			b.WriteString(fit(" "+mark+c.name+"  "+c.desc, a.Width-1) + "\n")
		}
	}
	b.WriteString(a.Input.View() + "\n")
	if a.Status != "" {
		b.WriteString(colDim.Render(fit(" "+a.Status, a.Width-1)) + "\n")
	} else {
		b.WriteString("\n")
	}
	b.WriteString(colDim.Render(fit(" tab panes · enter run/open · ? help · ctrl+c quit", a.Width-1)))
	return b.String()
}
