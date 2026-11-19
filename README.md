# smelt

**Smelt a slow, pure Python function into a verified Rust extension. Only proven metal ships.**

smelt takes ONE slow, pure Python function and freezes its real behavior into a
differential oracle: 200+ recorded input/output cases, hashed and read-only. A
model — **any model, any provider** (v0.8 removed the hardwired Gemma-4 defaults)
— writes an equivalent Rust extension (`pyo3`). **Code, not the model, checks
that the Rust answers identically on every recorded case.** Only then does smelt
time both and report the measured speedup with a confidence interval. Failing
rewrites are rejected — and since v0.8, attempt 2+ receives the concrete failure
evidence (compiler errors, mismatched cases) to repair itself. The Python
original stays as the fallback.

The honest claim: **no wrong rewrite is accepted on the tested inputs.**

Built live at **sudo Hacktober** (MLH · SRM AP Amaravati, Oct 10–11 2026, solo).

## Quickstart

```bash
git clone https://github.com/LangerSword/smelt.git && cd smelt
uv sync
uv run smelt doctor          # toolchain + provider check

# no network, no model — deterministic demo with a hand-provided candidate:
uv run smelt run examples/demo/run_length.py:rle_encode --provider fake \
  --candidate tests/fixtures/candidates/rle_encode_correct.rs

# with a provider key (e.g. NVIDIA_API_KEY in env or ~/.hermes/.env):
uv run smelt run examples/demo/run_length.py:rle_encode   # provider auto-resolves
uv run smelt report runs/<run-id>
```

Capture, verify and benchmark need no network. The v0.8.0 wheel and sdist build
green and install cleanly from disk: `uv tool install ./dist/smelt_rs-0.8.0-py3-none-any.whl`.
The PyPI upload is pending the maintainer's go (the name `smelt-rs` is unclaimed).

## Commands

| command | what it does |
|---|---|
| `smelt run file.py:fn` | full loop: purity → oracle → generate → build → verify → bench → report |
| `smelt capture file.py:fn` | freeze an oracle, no generation |
| `smelt resume runs/<id>` | continue an interrupted run (repair evidence reconstructed) |
| `smelt report runs/<id>` | print the run report (markdown) |
| `smelt scan <path>` | list candidates with tier + skip reasons (`--json` available) |
| `smelt apply runs/<id>` | VIEW ONLY: diff + fallback shim; never writes into your repo |
| `smelt doctor [--probe]` | environment + provider checks |
| `smelt evals` | run the frozen corpus (call cap + pause) |
| `smelt mcp` | serve smelt as an MCP server (stdio) for any coding agent |
| `smelt furnace` | launch the Go TUI if installed |

`smelt run` flags worth knowing: `--provider` (default: auto from your keys),
`--model`, `--repair/--no-repair` (evidence-fed attempts 2+, default on),
`--max-attempts`, `--cases`, `--seed`.

Exit codes: **0** accepted · **2** config error · **3** refused (impure or
unsupported shape, with a refactor hint) · **4** rejected (honest — mismatch or no
meaningful gain) · **5** harness error.

## Results (every number labeled with its model)

### v0.8 — model-agnostic pipeline (repair loop on)

Provider `nvidia` · model **`mistralai/mistral-large-4-1t-a52b`** — picked
empirically by the bake-off ([`evals/bakeoff-v08.json`](evals/bakeoff-v08.json):
4 models × 3 tasks, ranked by accepted tasks → provider calls → median speedup
lower bound; per-task wall-clock caps record NIM stalls as `timeout`).

- **Corpus, 24 tasks** ([`evals/results.md`](evals/results.md)): **10 accepted /
  0 rejected / 12 timeouts / 2 errors**, 44 calls. The 12 timeouts are NVIDIA
  NIM stalls on long generations (600s task cap), not pipeline failures; the 2
  errors are typed `finish_reason=length` (reasoning exhausted the token
  budget). Accepted median **2.29x**: collatz 7.80x · caesar 5.93x ·
  longest_alpha_run 3.44x · count_vowel_runs 2.33x · popcount 2.25x.
  `triangular` verified 209/209 and measured 19598x but is flagged
  **`timer_limited`** (O(1) closed form vs Python's loop; Rust median below the
  0.5 ms timer floor) — reported flagged, not as a headline.
- **Blind re-run** (same frozen list, [`evals/general-v08.md`](evals/general-v08.md)):
  0 accepted / 9 refused / 1 config error / 0 errors / 0 provider calls.
  Package loading now reaches the REAL boundaries: missing build artifacts
  (`humanize._version`) and third-party deps — the old ImportError wall is gone.
- **Meta-eval (false-accept gate)**: **22/22** hand-written wrong rewrites
  rejected on merits across five batteries (str, multi-param, tuple-arg,
  list[float], tuple-return incl. a wrong-container candidate) —
  [`scripts/meta_eval.py`](scripts/meta_eval.py). Each widening was observed
  RED before its support landed.
- **Tests**: 87 pytest (repair loop, package loading, float lists, tuple
  returns, domain guard, providers, agent API, MCP) + 66 Go (incl. goldens over
  a real repair run). CI on every push.
- **Plugin layer**: `smelt mcp` (MCP server, zero extra deps), Hermes plugin
  (10 tools + approval hook, `hermes plugins validate` passes), Claude Code
  plugin (commands + PostToolUse hint hook + `.mcp.json`) —
  [`docs/agent-integration.md`](docs/agent-integration.md).

### Historical — Gemma-4 era (pre-v0.8, kept verbatim)

Provider `gemini` · model **`gemma-4-26b-a4b-it`** (the former default; removed
in v0.8). These tables are the event-era record, labeled with their model.

- **Corpus, 24 tasks, two full runs**: 20 accepted / 4 rejected / 0 errors
  (36 calls, median 2.83x) and 23 accepted / 1 rejected / 0 errors (27 calls,
  median 2.72x). Full tables: [`evals/results-gemma.md`](evals/results-gemma.md) ·
  [`evals/results-after.md`](evals/results-after.md).
  Why the two runs differ: each run draws a fresh random seed and the model
  samples — the single-parameter generator is byte-identical, prompts and scaffold
  untouched. The three status flips (1.38–1.46x → 1.59–1.62x) sit at the 1.5x
  acceptance boundary.
- **Highlights**: `triangular` 47.14x · `collatz_steps` 22.68x · `caesar_shift`
  11.51x. Rejections stay at 1.22–1.46x — never reported as wins.
- **Local arm** (`gemma-4-e2b-qat` via llama.cpp, fully offline): 18 accepted /
  6 rejected / 0 errors — [`evals/results-local.md`](evals/results-local.md).
- **Meta-eval at the time**: 16/16 wrong rewrites rejected (extended to 22/22
  in v0.8).
- **Blind test** (3 real open-source repos, 10 functions, list frozen before the
  run): **0 accepted, 9 refused, 1 config error, 0 errors, 0 provider calls.**
  Refusal reasons: 6 package layouts (relative imports), 2 impurity, 1 unsupported
  type; the config error is a dotted qualname (exit 2). This showed **safety, not
  generality**. The v0.8 re-run ([`evals/general-v08.md`](evals/general-v08.md))
  measures what package loading changed — same frozen list, no tuning.
  [`evals/general.md`](evals/general.md)

## Providers

Model-agnostic since v0.8 — no model family is hardwired.

| provider | endpoint | model | key |
|---|---|---|---|
| `nvidia` | NVIDIA NIM (OpenAI-compatible) | default picked empirically by [`scripts/model_bakeoff.py`](scripts/model_bakeoff.py); any NIM chat model via `--model` | `NVIDIA_API_KEY` |
| `gemini` | Google AI Studio, native REST | required (`--model` / `SMELT_GEMINI_MODEL`) | `GEMINI_API_KEY` / `GOOGLE_API_KEY` |
| `local` | llama.cpp / any OpenAI-compatible server | server's model (name ignored) | none |
| `do` | DigitalOcean Inference | required | `DIGITALOCEAN_TOKEN` |
| `openai` / `openrouter` | any OpenAI-compatible endpoint | required | `SMELT_OPENAI_KEY` → `OPENAI_API_KEY` / `OPENROUTER_API_KEY` |
| `file` / `fake` | hand-provided candidates, consumed in order across attempts | — | gate runs + CI |

`--provider` omitted → `SMELT_PROVIDER` → first provider with a key → local.
`--model` omitted → `SMELT_MODEL` → `SMELT_<PROVIDER>_MODEL` → provider default.
Secrets resolve env → project `.env` → `~/.hermes/.env`; they are never logged,
printed or committed. Details: [`docs/providers.md`](docs/providers.md).

## Agent integration — plugin anywhere

One stdlib-only handler core behind three surfaces (no second implementation):

- **MCP server** — `smelt mcp` (zero extra dependencies): 10 tools incl.
  detached run jobs with poll/kill/mtime-verify. Works with Claude Code,
  Cursor, OpenCode, Goose, Hermes — any MCP-capable agent.
- **Hermes plugin** — [`plugin/`](plugin/README.md): the same 10 tools + a
  `pre_tool_call` approval hook for mutating verbs + the bundled skill.
- **Claude Code plugin** — this repo: `.claude-plugin/`, `/smelt-scan`
  `/smelt-run` `/smelt-report` commands, a PostToolUse hook that surfaces
  smelt-able candidates after Python edits (never runs anything unprompted),
  the skill, and `.mcp.json`.
- **Any other agent** — the validated Agent Skill (`skills/smelt`) or the
  plain `--json` CLI with typed exit codes.

Setup + security notes: [`docs/agent-integration.md`](docs/agent-integration.md).

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
          NVIDIA_API_KEY: ${{ secrets.NVIDIA_API_KEY }}   # or any supported provider key
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

- Parameters: `str/int/float/bool/list[int]/list[float]/list[str]/tuple[int, int]`,
  any number of positional parameters. Returns: the same set plus `tuple[int, int]`
  (v0.8 — with true tuple-vs-list fidelity: a `Vec` return where Python returns a
  tuple is rejected). Anything else: typed refusal + refactor hint, never a crash.
- Package layouts with relative imports ARE supported (v0.8): targets load in
  their package context. Unresolvable imports / missing third-party deps: typed
  refusal with a hint.
- Integers are tested inside i64. Targets whose recorded outputs leave i64 are
  refused AT CAPTURE with a hint (v0.8 domain guard) — no wasted model calls, no
  misleading mismatch. Big-int domains remain an open policy; never silently
  truncated.
- The oracle proves equivalence **on the tested inputs** — exactly that claim.
- Tiny functions can legitimately fail to beat pyo3 overhead (`manhattan` verifies
  every case, then is honestly rejected near 1.0x).
- Targets that raise on edge cases are fully supported (v0.8): outcome parity in
  verify, exceptions discarded identically on both sides in bench.

## Docs

[`docs/how-it-works.md`](docs/how-it-works.md) · [`docs/cli.md`](docs/cli.md) ·
[`docs/providers.md`](docs/providers.md) · [`docs/safety.md`](docs/safety.md) ·
[`docs/evals.md`](docs/evals.md) · [`docs/faq.md`](docs/faq.md) ·
[`docs/events.md`](docs/events.md) · [`docs/bot-integration.md`](docs/bot-integration.md)
(workflow + CI design, not yet built) · [`AI_USE.md`](AI_USE.md) (build agent vs
human; runtime model disclosure) · [`EXPLAIN.md`](EXPLAIN.md) (deep dive).

## License

MIT.
