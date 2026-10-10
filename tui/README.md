# furnace

Read-only terminal UI for [smelt](../README.md) runs — a **front end**. The
Python core is the source of truth: furnace reads `runs/<id>/events.jsonl`
(+ `state.json`, contract in [`docs/events.md`](../docs/events.md)) and renders
the loop. It never runs generated code and never reads or prints secrets.

## Build & run

```bash
cd tui
go build -o furnace .        # requires Go 1.27+
./furnace replay ../runs/261011-024849-b4f411
```

Keys: `q` quit · `tab` switch pane · `↑`/`↓` (also `pgup`/`pgdn`) scroll the
log when focused. The footer states the schema version.

What it shows:

- the loop as a horizontal flow — `select → oracle → generate → build → verify
  → bench → verdict` (`✔` reached, `·` not, `★` terminal verdict);
- a results panel — oracle cases, speedup with the conservative lower bound,
  attempts, target, provider and the exact model label;
- a log pane — build errors, verify mismatches, safety violations, halts;
- the final verdict — **INGOT** (accepted), **SLAG** (rejected), **ASH**
  (refused/error), **COLD** (run killed mid-flight). Never colour-only: every
  state has a word.

## Tests

```bash
go test ./...                       # unit + teatest goldens + 80-col case
go test ./internal/replay -update   # regenerate goldens after a deliberate change
```

Fixtures under `testdata/runs/` are real run slices: three REAL Gemini runs
(`gemma-4-26b-a4b-it`: accepted / rejected / refused) plus one file-provider
unit fixture with no model involved — provenance in
[`testdata/runs/README.md`](testdata/runs/README.md).

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
