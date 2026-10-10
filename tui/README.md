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

Keys: `q` quit (during a live run it stops the run first) · `tab` switch pane ·
`↑`/`↓` (also `pgup`/`pgdn`) scroll the log when focused. The footer states the
schema version.

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
go test ./...                       # 26 tests: unit + teatest + fake-smelt suite
go test ./internal/replay -update   # regenerate goldens after a deliberate change
```

Fixtures under `testdata/runs/` are real run slices: three REAL Gemini runs
(`gemma-4-26b-a4b-it`: accepted / rejected / refused) plus one file-provider
unit fixture with no model involved — provenance in
[`testdata/runs/README.md`](testdata/runs/README.md). `testdata/fake-smelt.sh`
is the deterministic fake (dispatch: run / scan / doctor / apply) used by the
tests — no API calls. Note: the suite runs locally today; the Go test job in
CI lands with T4.

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
