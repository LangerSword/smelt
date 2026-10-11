# smelt

**Smelt a slow, pure Python function into a verified Rust extension. Only proven metal ships.**

smelt takes ONE slow, pure Python function and freezes its real behavior into a
differential oracle: 200+ recorded input/output cases, hashed and read-only. A model
(**Gemma 4** via the Gemini API — or any configured provider) writes an equivalent
Rust extension (`pyo3`). **Code, not the model, checks that the Rust answers
identically on every recorded case.** Only then does smelt time both and report the
measured speedup with a confidence interval. Failing rewrites are rejected. The
Python original stays as the fallback.

The honest claim: **no wrong rewrite is accepted on the tested inputs.**

Built live at **sudo Hacktober** (MLH · SRM AP Amaravati, Oct 10–11 2026, solo).

## Quickstart

```bash
git clone https://github.com/LangerSword/smelt.git && cd smelt
uv sync
uv run smelt doctor          # toolchain + provider check
uv run smelt run examples/demo/run_length.py:rle_encode --provider gemini
uv run smelt report runs/<run-id>
```

The v0.6.0 wheel and sdist build green and install cleanly from disk:
`uv tool install ./dist/smelt_rs-0.6.0-py3-none-any.whl`. The PyPI upload is
pending the maintainer's go (the name `smelt-rs` is unclaimed). Capture, verify
and benchmark need no network.

## Commands

| command | what it does |
|---|---|
| `smelt run file.py:fn` | full loop: purity → oracle → generate → build → verify → bench → report |
| `smelt capture file.py:fn` | freeze an oracle, no generation |
| `smelt resume runs/<id>` | continue an interrupted run |
| `smelt report runs/<id>` | print the run report (markdown) |
| `smelt scan <path>` | list candidates with tier + skip reasons (`--json` available) |
| `smelt apply runs/<id>` | VIEW ONLY: diff + fallback shim; never writes into your repo |
| `smelt doctor [--probe]` | environment + provider checks |
| `smelt evals` | run the frozen corpus (call cap + pause) |
| `smelt furnace` | launch the Go TUI if installed |

Exit codes: **0** accepted · **2** config error · **3** refused (impure or
unsupported shape, with a refactor hint) · **4** rejected (honest — mismatch or no
meaningful gain) · **5** harness error.

## Results (every number labeled with its model)

Provider `gemini` · model **`gemma-4-26b-a4b-it`** (default; free-tier friendly).

- **Corpus, 24 tasks, two full runs**: 20 accepted / 4 rejected / 0 errors
  (36 calls, median 2.83x) and 23 accepted / 1 rejected / 0 errors (27 calls,
  median 2.72x). Full tables: [`evals/results.md`](evals/results.md) ·
  [`evals/results-after.md`](evals/results-after.md).
  Why the two runs differ: each run draws a fresh random seed and the model
  samples — the single-parameter generator is byte-identical, prompts and scaffold
  untouched. The three status flips (1.38–1.46x → 1.59–1.62x) sit at the 1.5x
  acceptance boundary.
- **Highlights**: `triangular` 47.14x · `collatz_steps` 22.68x · `caesar_shift`
  11.51x. Rejections stay at 1.22–1.46x — never reported as wins.
- **Local arm** (`gemma-4-e2b-qat` via llama.cpp, fully offline): 18 accepted /
  6 rejected / 0 errors — [`evals/results-local.md`](evals/results-local.md).
- **Meta-eval (false-accept gate)**: 13/13 hand-written wrong rewrites rejected —
  [`scripts/meta_eval.py`](scripts/meta_eval.py). (A tuple battery — 16/16 — sits
  on `feature/general`, unmerged.)
- **Blind test** (3 real open-source repos, 10 functions, list frozen before the
  run): **0 accepted, 9 refused, 1 config error, 0 errors, 0 provider calls.**
  Refusal reasons: 6 package layouts (relative imports), 2 impurity, 1 unsupported
  type; the config error is a dotted qualname (exit 2). This shows **safety, not
  generality**: every outcome is typed, nothing crashed, nothing was accepted — the
  list is honestly non-convertible today. [`evals/general.md`](evals/general.md)

## Providers

| provider | model | status |
|---|---|---|
| `gemini` — Google AI Studio | `gemma-4-26b-a4b-it` (default), `gemma-4-31b-it` (strongest, slower) | used for all results above |
| `local` — llama.cpp / any OpenAI-compatible server | any local model | working, fully offline |
| `do` — DigitalOcean Inference | `gemma-4-31B-it` | wired; activates with `DIGITALOCEAN_TOKEN` |
| `file` / `fake` | hand-provided candidates | gate runs + CI |

Secrets resolve env → project `.env` → `~/.hermes/.env`; they are never logged,
printed or committed.

## TUI — Furnace (Go)

[`tui/`](tui/README.md) replays finished runs and starts live ones. It reads
`runs/<id>/events.jsonl`; it never runs generated code and never reads secrets.

```bash
cd tui && go build -o furnace .
./furnace replay ../runs/<id>      # INGOT · SLAG · ASH
./furnace run ../examples/demo/run_length.py:rle_encode --provider gemini
```

26 tests (build + vet + test run in CI) · demo GIF from real frames:
[`tui/testdata/demo.gif`](tui/testdata/demo.gif).

## Agent skill

[`skills/smelt/SKILL.md`](skills/smelt/SKILL.md) — Agent Skills open standard,
validated (`agentskills validate ./skills/smelt` → exit 0). Any coding agent that
supports Agent Skills can load it and run the smelt loop (scan → capture →
generate → verify → bench).

## Use smelt as a workflow

Three ways to run the loop, smallest first.

1. **Manual** — `smelt scan <path>` lists candidates, `smelt run <file.py:fn>`
   runs the loop, `smelt apply runs/<id>` prints the diff. You review it and
   open the PR yourself. Apply never writes anything.
2. **Agent** — install the skill (`skills/smelt`, Agent Skills format) and ask
   your coding agent to "speed up this function the smelt way". The agent runs
   scan → run → review and hands you the diff.
3. **CI / bot (CodeRabbit-style)** — trigger on a PR label or manual dispatch.
   Scan the changed files. Run at most 3 candidates. Post one PR comment with
   a results table and the diff. Never push. No secrets for fork PRs. Call
   caps keep the free tier safe.

**The GitHub Action is design, not yet built.** No workflow is installed in
`.github/workflows/`, and `tools/bot_run.py` does not exist yet; the reference
below must be built and tested on a scratch repo first. Design notes:
[`docs/bot-integration.md`](docs/bot-integration.md).

### Reference workflow (design — not yet built)

```yaml
name: smelt-bot
on:
  pull_request:
    types: [labeled]
  workflow_dispatch:
permissions:
  contents: read
  pull-requests: write
concurrency:
  group: smelt-bot-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: true
jobs:
  suggest:
    if: github.event.label.name == 'smelt-me' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: astral-sh/setup-uv@v5
      - run: uv tool install git+https://github.com/LangerSword/smelt
      - name: Scan (tier-1 candidates, capped at 3)
        run: smelt scan . --json > scan.json
      - name: Run (same-repo PRs only)
        if: ${{ github.event.pull_request.head.repo.full_name == github.repository || github.event_name == 'workflow_dispatch' }}
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python tools/bot_run.py scan.json --max 3 --out comment.md
      - name: Comment once
        run: gh pr comment ${{ github.event.pull_request.number }} --body-file comment.md
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

What each step does:

| step | what it does |
|---|---|
| trigger | fires only on the `smelt-me` label or a manual dispatch — never on every push (a run costs model calls and a Rust build) |
| toolchains | installs Rust, uv and the smelt CLI (pin a tag before enabling) |
| scan | lists candidates; the bot keeps tier-1 functions in files the PR touched, capped at 3 |
| run | one `smelt run` per candidate; skipped on fork PRs, so no secret is ever exposed |
| comment | exactly one PR comment: results table (status · exit code · speedup lb · attempts · model) + view-only diffs + reproduce commands |
| safety | the job never writes to the branch (`contents: read`); a concurrency group cancels duplicate runs |

## Safety (generated Rust is untrusted)

- Pinned scaffold (pyo3 `=0.29.3`); the model fills one function body only. A
  static scan runs before every build and rejects `unsafe`, extra crates,
  `build.rs`, net/process/fs, `include_*!`, `env!`.
- Builds run in scratch dirs; execution happens in a separate worker under
  resource limits. Rust panics become Python exceptions — recorded, never a
  process abort.
- smelt never writes into your project. `apply` is view only.

## Honest limits

- One argument of `str/int/float/bool/list[int]/list[str]`; multi-parameter
  targets work too. `tuple[int, int]` is on `feature/general`, unmerged. Anything
  else: typed refusal + refactor hint, never a crash.
- Integers are tested inside i64. Inputs whose Python result exceeds i64 (e.g.
  `i64::MIN // -1`) cannot be matched by an i64 rewrite — such candidates are
  honestly rejected; the domain policy is open.
- The oracle proves equivalence **on the tested inputs** — exactly that claim.
- Tiny functions can legitimately fail to beat pyo3 overhead (`manhattan` verifies
  208/208, then is rejected at 1.43x).
- Package layouts (relative imports) are not supported yet — typed refusal with a
  hint.

## Docs

[`docs/how-it-works.md`](docs/how-it-works.md) · [`docs/cli.md`](docs/cli.md) ·
[`docs/providers.md`](docs/providers.md) · [`docs/safety.md`](docs/safety.md) ·
[`docs/evals.md`](docs/evals.md) · [`docs/faq.md`](docs/faq.md) ·
[`docs/events.md`](docs/events.md) · [`docs/bot-integration.md`](docs/bot-integration.md)
(workflow + CI design, not yet built) · [`AI_USE.md`](AI_USE.md) (build agent vs
human; runtime model disclosure) · [`EXPLAIN.md`](EXPLAIN.md) (deep dive).

## License

MIT.
