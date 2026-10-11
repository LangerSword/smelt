# furnace

Terminal UI for [smelt](../README.md) runs — a **front end**. The Python core is
the source of truth: furnace reads `runs/<id>/events.jsonl` (+ `state.json`,
contract in [`docs/events.md`](../docs/events.md)) and renders the loop. It never
runs generated code and never reads or prints secrets.

## Build & run

```bash
cd tui
go build -o furnace .        # requires Go 1.27+

# home screen: prompt box · scan · pick · run · history
./furnace

# replay a finished run
./furnace replay ../runs/261011-024849-b4f411

# run smelt live and watch it
./furnace run ../examples/demo/run_length.py:rle_encode \
      --provider gemini --model gemma-4-26b-a4b-it
```

## One-command install

```bash
go install github.com/LangerSword/smelt/tui@main
```

The binary lands in `$(go env GOPATH)/bin/furnace`. While the UX branch is open,
use `@feature/furnace-ux`. Release binaries via `gh release` are planned; the
PyPI `smelt-rs` package and the `smelt furnace` launcher stay the Python side's
job (this TUI must not depend on them to build).

## UX layout (v0.7)

- **Header** (persistent): FURNACE v0.7 · run id · provider · model.
- **Two columns when width ≥ 100** (stacked below): left = the loop flow
  (`select → … → verdict` with heating/poured marks) + verdict + results;
  right = live panel — oracle progress bar, cases passed, attempts, speedup
  with lower bound, and the last build/verify message.
- **Transcript** with timestamps; error lines carry a `✗` label. `j/k`,
  `↑/↓`, `pgup/pgdn` scroll from either focus.
- **Composer**: slash-command autocomplete (tab completes, arrows choose,
  esc cancels), prompt history (↑/↓).
- **Overlays**: `?` help · `/provider`, `/model`, `/sessions` (`ctrl+r`)
  pickers · `d` view-only diff with added-line colouring.
- **Result screen** (`r`; also auto-opened when a live run ends
  accepted/rejected): four tabs — `summary` (verdict, oracle cases, speedup
  with the conservative lower bound, attempts, model, time), `rust` (the
  final `lib.rs` with line numbers and simple syntax colouring; SLAG marks it
  a *rejected candidate*; ASH shows the refusal reason + refactor hint),
  `compare` (Python original vs Rust, two columns when width ≥ 120, stacked
  below, one shared scroll), `diff` (the view-only `smelt apply` diff — new
  crate file + shim, +/- colouring, build command, revert note). An
  **attempts strip** below the tabs shows each attempt's outcome — compile
  error / mismatch with the first failing input, expected and got / no gain /
  accepted — so the feedback loop stays visible. Everything is read from
  `runs/<id>/` artifacts only; a missing artifact renders a clear message,
  never a crash.
- **Status line**: state (ready/running/waiting for the model/done) · elapsed ·
  verdict word. Colour never carries meaning; `--no-anim`, `NO_COLOR` and
  `TERM=dumb` respected. Renders at 80×24 and 160×45; resize-safe.

Keys: `q` quit (during a live run it stops the run first) · `tab` focus/complete ·
`↑/↓`/`j/k` (also `pgup`/`pgdn`) scroll · `esc` back/cancel · `r` result
(tabs: `1-4` / `←→`, `tab` next, `esc`/`r` back) · `ctrl+c` once stops
a live run (confirm line), twice quits · `d` diff · `ctrl+r` sessions ·
`?` help overlay. `--no-anim` freezes the heat-pulse (also automatic with
`NO_COLOR` or `TERM=dumb`).

What it shows:

- the loop as a horizontal flow — `select → oracle → generate → build → verify
  → bench → verdict` (`✔` poured, `◐` heating, `·` cold, `★` terminal verdict);
- a results panel — oracle cases, speedup with the conservative lower bound,
  attempts, target, provider and the exact model label;
- a log pane — build errors, verify mismatches, safety violations, halts
  (unparsed stream lines are skipped, counted and logged);
- the final verdict — **INGOT** (accepted), **SLAG** (rejected), **ASH**
  (refused/error), **COLD** (run killed mid-flight). Never colour-only: every
  state has a word.

## Home screen (`furnace`)

The interactive layer, in the style of Hermes' prompt box:

- **prompt box** — type a slash command or a bare `file.py:fn` target;
- **`/scan <path>`** — lists candidates from `smelt scan --json` with skip
  reasons (e.g. "relative imports — package loading not supported yet");
  `enter` on a candidate starts the run (the scan root is joined into the path);
- **`/run <target> [--provider p] [--model m]`**, **`/resume <run-dir>`**,
  **`/report <run-dir>`**, **`/provider <name> [model]`** (bare: availability
  from `smelt doctor --json`), **`/doctor`**, **`/help`**, **`/quit`**;
- **recent runs** — history from the runs directory; `enter` opens the run;
- **`d`** in a run view — the view-only diff from `smelt apply` (it never
  writes into the target repo).

Home keys: `tab` panes · `↑/↓` select · `enter` run/open · `ctrl+c` quit.

## Live runs (`furnace run`)

`furnace run <file.py:fn>` starts `smelt run … --json` as a subprocess,
discovers the new run directory, and tails its `events.jsonl` — the flow heats
as events land, attempts and feedback loops show up as they happen, and a
"waiting for the model…" status appears when generation takes longer than a few
seconds (which also covers provider retry waits). `q` / `Ctrl-C` stops the run
**including its whole process group** (no orphan cargo/worker processes) and
prints the exact `smelt resume runs/<id>` command.

Flags: `--provider`, `--model`, `--smelt <path>` (default: `smelt` on PATH),
`--runs-dir` (default `runs`, relative to the current directory — run furnace
from your project root).

## Tests

```bash
go test ./...                       # 58 tests: unit + teatest goldens (run + result screens) + fake-smelt suite
go test ./internal/replay -update   # regenerate goldens after a deliberate change
```

Fixtures under `testdata/runs/` are real run slices: REAL Gemini runs
(`gemma-4-26b-a4b-it`: accepted / rejected / refused, incl. one refusal with a
refactor hint), a file-provider mismatch run (**no model**), a sliced run that
pins the missing-artifact path, and one file-provider unit fixture — each
labeled with its model in
[`testdata/runs/README.md`](testdata/runs/README.md). Result-screen fixtures
store the target path run-relative (`source/…`) so goldens render identically
everywhere; the recorded sha256 must match the copied source.
`testdata/fake-smelt.sh` is the deterministic fake (dispatch: run / scan /
doctor / apply) used by the tests — no API calls. The suite runs locally
**and in CI** (the `go` job in
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml): build + vet + test).

## Demo assets

- [`testdata/demo.gif`](testdata/demo.gif) — a short loop rendered from **real
  captured session frames** (home banner → heating → INGOT (local) → INGOT
  (gemini) → history).
- [`testdata/demo.tape`](testdata/demo.tape) — the VHS script for a full
  recording (replay accepted → replay refused → live local run). Recording
  needs `vhs`, `ttyd` and `ffmpeg` on PATH; vhs/ttyd were not installed on the
  build machine, so the tape is committed ready-to-record:
  `go install github.com/charmbracelet/vhs@latest`, install ttyd, then
  `vhs tui/testdata/demo.tape` from the repo root.

## Licenses (verified from module-cache LICENSE files)

| component | version | license | released |
|---|---|---|---|
| Go toolchain (build) | 1.27.1 (`linux/amd64`) | BSD-3-Clause | installed on this machine |
| [bubbletea](https://github.com/charmbracelet/bubbletea) | v1.3.10 | MIT | 2025-09-17 |
| [lipgloss](https://github.com/charmbracelet/lipgloss) | v1.1.0 | MIT | 2025-03-12 |
| [bubbles](https://github.com/charmbracelet/bubbles) | v1.0.0 | MIT | 2026-02-09 |
| [teatest](https://github.com/charmbracelet/x/tree/main/exp/teatest) | v0.0.0-20261008172826-faa4adf95555 | MIT | 2026-10-08 |

`go mod tidy` resolves the rest of the tree (`x/ansi`, `x/cellbuf`,
`colorprofile`, `termenv`, … — all MIT/BSD-family; `go-licenses` or the module
cache can be used for a full audit).
