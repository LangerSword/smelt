# smelt

**Smelt a slow pure Python function into a verified Rust extension. Only proven metal ships.**

smelt takes ONE slow, pure Python function and freezes what it actually does into a
differential oracle — 200+ recorded input/output cases, hashed and read-only. A model
(**Gemma 4 via the Gemini API**, or any configured provider) writes an equivalent Rust
extension (`pyo3`). **Code, not the model, checks that the Rust answers identically on
every recorded case.** Only then does smelt time both implementations and report the
measured speedup, with a confidence interval. Anything that fails the oracle or shows no
real gain is rejected. The original Python function stays on as the fallback.

The honest claim: **no wrong rewrite is accepted on the tested inputs.**

smelt is a metalworking metaphor, not a networking tool.

> Status: built live at **sudo Hacktober** (MLH, SRM AP Amaravati), Oct 10–11 2026, solo.
> **v0.6.0** — core loop + CLI + evals + validated agent skill + Furnace TUI +
> multi-parameter oracle (wheel/sdist built and install-verified; PyPI upload pending).

## How it works

```
select ─▶ capture oracle ─▶ generate ─▶ build ─┬─ok─▶ verify ─┬─pass─▶ bench ─▶ accept ─▶ report
                          (model writes       │            │
                           lib.rs)            └─ errors ────┴─ mismatches ─▶ feed back ↺ (max 3 attempts)
                                                                             else reject (honest)
```

The orchestrator is deterministic; the model only acts inside `generate`. Transitions are
checkpointed (`state.json` + `events.jsonl`), so runs resume.

## Results — eval corpus (generated, never hand-edited)

Source: [`evals/results.md`](evals/results.md) · produced by `gemini` · `gemma-4-26b-a4b-it` on a laptop ·
**24 tasks · 20 accepted · 4 rejected (honest, no meaningful gain) · 0 errors ·
provider calls: 36 attempts (cap 120)**

| function | cat | status | attempts | oracle | speedup | lb | notes |
|---|---|---|---|---|---|---|---|
| `linear_score` | float | rejected | 3 | 206 | 1.41x | 1.37x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.41x, l |
| `sigmoid_approx` | float | accepted | 2 | 206 | 1.65x | 1.60x | verified 206/206 cases; speedup 1.65x (conservative lower bound 1.60x) |
| `collatz_steps` | int | accepted | 1 | 209 | 22.68x | 21.79x | verified 209/209 cases; speedup 22.68x (conservative lower bound 21.79x) |
| `digital_root` | int | accepted | 1 | 209 | 3.32x | 3.24x | verified 209/209 cases; speedup 3.32x (conservative lower bound 3.24x) |
| `popcount` | int | accepted | 1 | 209 | 4.99x | 4.72x | verified 209/209 cases; speedup 4.99x (conservative lower bound 4.72x) |
| `reverse_digits` | int | accepted | 1 | 209 | 2.19x | 2.16x | verified 209/209 cases; speedup 2.19x (conservative lower bound 2.16x) |
| `sum_digits_sq` | int | accepted | 1 | 209 | 3.01x | 2.83x | verified 209/209 cases; speedup 3.01x (conservative lower bound 2.83x) |
| `triangular` | int | accepted | 1 | 209 | 47.14x | 46.97x | verified 209/209 cases; speedup 47.14x (conservative lower bound 46.97x) |
| `bucket_hash` | list | accepted | 2 | 204 | 2.23x | 2.17x | verified 204/204 cases; speedup 2.23x (conservative lower bound 2.17x) |
| `count_peaks` | list | accepted | 1 | 204 | 2.13x | 2.02x | verified 204/204 cases; speedup 2.13x (conservative lower bound 2.02x) |
| `longest_run` | list | accepted | 2 | 204 | 1.64x | 1.54x | verified 204/204 cases; speedup 1.64x (conservative lower bound 1.54x) |
| `max_subarray` | list | accepted | 1 | 204 | 1.72x | 1.56x | verified 204/204 cases; speedup 1.72x (conservative lower bound 1.56x) |
| `median_doubled` | list | rejected | 3 | 204 | 1.38x | 1.35x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.38x, l |
| `prefix_max_sum` | list | rejected | 3 | 204 | 1.46x | 1.41x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.46x, l |
| `sum_squares` | list | accepted | 1 | 204 | 1.74x | 1.66x | verified 204/204 cases; speedup 1.74x (conservative lower bound 1.66x) |
| `caesar_shift` | string | accepted | 1 | 225 | 11.51x | 11.48x | verified 225/225 cases; speedup 11.51x (conservative lower bound 11.48x) |
| `count_vowel_runs` | string | accepted | 1 | 225 | 5.96x | 5.28x | verified 225/225 cases; speedup 5.96x (conservative lower bound 5.28x) |
| `count_words` | string | accepted | 1 | 225 | 7.36x | 6.74x | verified 225/225 cases; speedup 7.36x (conservative lower bound 6.74x) |
| `is_palindrome_norm` | string | accepted | 1 | 225 | 2.40x | 2.39x | verified 225/225 cases; speedup 2.40x (conservative lower bound 2.39x) |
| `longest_alpha_run` | string | accepted | 1 | 225 | 6.77x | 6.30x | verified 225/225 cases; speedup 6.77x (conservative lower bound 6.30x) |
| `normalize_spaces` | string | rejected | 3 | 225 | 1.22x | 1.20x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.22x, l |
| `reverse_words` | string | accepted | 1 | 225 | 1.61x | 1.58x | verified 225/225 cases; speedup 1.61x (conservative lower bound 1.58x) |
| `snake_to_camel` | string | accepted | 1 | 225 | 2.66x | 2.49x | verified 225/225 cases; speedup 2.66x (conservative lower bound 2.49x) |
| `top_word` | string | accepted | 2 | 225 | 4.96x | 4.74x | verified 225/225 cases; speedup 4.96x (conservative lower bound 4.74x) |

Meta-eval (false-accept gate): **10/10 hand-written wrong rewrites rejected** — [`scripts/meta_eval.py`](scripts/meta_eval.py).
_Local-model arm (`gemma-4-e2b-qat` via llama.cpp, fully offline): **18 accepted / 6 rejected / 0 errors of 24 tasks** — 44 provider calls; full table in `evals/results-local.md`._

**Model story (one story, kept consistent):** `gemma-4-26b-a4b-it` is the default — fast and
free-tier friendly; every result in this repo (evals, TUI fixtures, gate runs) was produced
with it, and the demo uses it. `gemma-4-31b-it` remains available for the strongest output
when the wait is worth it (slower per call; it powered the one v0.2 gate spot-check).

Every number is labeled with the model that produced it; nothing is rounded up (the CI
lower bound sits next to every speedup, and the acceptance rule reads it, not the median).

## Quickstart (from source)

```bash
git clone https://github.com/LangerSword/smelt.git && cd smelt
uv sync                                   # Python 3.11 + deps
uv run smelt doctor                       # toolchain + providers check
uv run smelt run examples/demo/run_length.py:rle_encode \
      --provider gemini --model gemma-4-26b-a4b-it
uv run smelt report runs/<run-id>
```

`uv tool install smelt-rs` works once the PyPI release is out. The v0.6.0
wheel and sdist build green and install cleanly from disk
(`uv tool install ./dist/smelt_rs-0.6.0-py3-none-any.whl`); the PyPI upload is
pending the maintainer's go (name `smelt-rs` is unclaimed). Verify/benchmark
steps never need the network; model runs need a provider (see below).

## Docs

- [`docs/how-it-works.md`](docs/how-it-works.md) — the pipeline, oracle, acceptance
- [`docs/cli.md`](docs/cli.md) — every command, flag and exit code
- [`docs/providers.md`](docs/providers.md) — providers, models, secrets policy
- [`docs/safety.md`](docs/safety.md) — untrusted-code handling and boundaries
- [`docs/evals.md`](docs/evals.md) — corpus, meta-eval, blind test
- [`docs/faq.md`](docs/faq.md) — common questions, honest limits
- [`docs/events.md`](docs/events.md) — the events.jsonl contract (TUI input)

## Commands

| command | what it does |
|---|---|
| `smelt run file.py:fn` | full loop: purity → oracle → generate → build → verify → bench → report |
| `smelt capture file.py:fn` | freeze an oracle without generation |
| `smelt resume runs/<id>` | continue an interrupted run (re-validates hashes) |
| `smelt report runs/<id>` | print the run report (markdown) |
| `smelt doctor [--probe]` | environment + provider checks; `--probe` sends tiny live calls |
| `smelt evals` | run the frozen corpus sequentially (call cap + pause); writes results.json/md |

Exit codes: 0 accepted · 3 refused (impure) · 4 rejected · 5 harness error · 2 config.

## Safety (generated Rust is untrusted)

- Scaffold + `Cargo.toml` are pinned (pyo3 `=0.29.3`) and supplied by smelt — the model
  fills in one function body only. Static scan before build rejects: `unsafe`, extra
  crates, `build.rs`, std net/process/fs, `include_*!`, `env!`.
- Builds happen in run-scratch dirs; the extension executes in a separate worker process
  under resource limits. smelt never writes into your project.
- Secrets resolve env → project `.env` → `~/.hermes/.env`; never logged.

## Providers

| Provider | Model | Status |
|---|---|---|
| `gemini` — Google AI Studio (native REST) | `gemma-4-26b-a4b-it` (default — free-tier friendly), `gemma-4-31b-it` (strongest, slower) | **working** — used for all results above |
| `local` — llama.cpp / OpenAI-compatible | any local model | working (offline fallback) |
| `do` — DigitalOcean Inference | `gemma-4-31B-it` | wired; activates with `DIGITALOCEAN_TOKEN` |
| `openai` — any OpenAI-compatible endpoint | set per provider | wired |
| `file` / `fake` | hand-provided / CI candidates | working |

## Honest limits

- Up to N parameters of simple types (str / int / float / bool / list[int] / list[str]);
  multi-parameter oracles use independent random columns + a capped edge product
  (~40–140 cases). Known domain gap: inputs whose Python result exceeds the i64 range
  (e.g. `i64::MIN // -1`, or a product of two extreme values) cannot be matched by an
  i64 rewrite — such candidates are honestly rejected; the domain-policy decision is
  with the developer.
- Integers are tested inside the 64-bit range; big Python ints are outside the tested
  domain and are never silently truncated.
- The oracle proves equivalence **on the tested inputs** — the claim is exactly that.
- Small functions can legitimately fail to beat pyo3 call overhead — four corpus tasks
  were rejected at 1.22–1.46x rather than reported as wins.
- Gemma 4's thinking mode is ON by default upstream; smelt pins `thinkingLevel: minimal`
  (otherwise calls can take minutes).

## Libraries (with licenses)

typer (MIT) · rich (MIT) · click (BSD-3) · pygments (BSD-2) · markdown-it-py (MIT) ·
pytest (MIT, dev) · pyo3 (MIT OR Apache-2.0) · maturin (MIT OR Apache-2.0) ·
llama.cpp (MIT, local model server) · Rust std (MIT OR Apache-2.0).
`uv tree` prints the full dependency tree.

## Agent skill

[`skills/smelt/SKILL.md`](skills/smelt/SKILL.md) follows the Agent Skills open standard.
Validated: `agentskills validate ./skills/smelt` → exit 0.

## TUI — Furnace (branch `feature/furnace`)

[`tui/`](tui/README.md) holds **Furnace**, a Go TUI that replays finished runs
and runs new ones live. It reads `runs/<id>/events.jsonl`: the loop as a
horizontal flow (`select → … → verdict`, ✔/·/◐/★), a results panel (oracle
cases, speedup with lower bound, attempts, exact model label), a log pane
(build errors, mismatches, halts) and the verdict — **INGOT** (accepted),
**SLAG** (rejected), **ASH** (refused/error). Furnace is a front end: the
Python core stays the source of truth, and it never runs generated code.

```bash
cd tui && go build -o furnace .          # Go 1.27+
./furnace                                # home: scan · pick · run · history
./furnace replay ../runs/<run-id>        # q quit · tab panes · ↑/↓ scroll
./furnace run ../examples/demo/run_length.py:rle_encode \
      --provider gemini --model gemma-4-26b-a4b-it    # live: flow heats as events land
```

The home screen is the interactive layer: prompt box with slash commands
(`/scan` with skip reasons, `/run`, `/resume`, `/report`, `/provider`,
`/doctor`, `/help`, `/quit`), a candidate picker, recent-run history, and a
view-only diff (`d` → `smelt apply`; never writes into the target).

Live mode starts `smelt run … --json` as a subprocess, tails the new run's
events stream, shows attempts and a "waiting for the model…" status during long
generations, and `q`/Ctrl-C stops the run (whole process group) printing the
`smelt resume` command — no orphan cargo/worker processes (verified).

Tests: **26** — run locally **and in CI** (the new `go` job: build + vet +
test). Demo: [`tui/testdata/demo.gif`](tui/testdata/demo.gif) (real captured
frames) + a ready-to-record VHS tape (`tui/testdata/demo.tape`).
`smelt furnace` launches the binary when installed, and `smelt doctor` reports
whether it is. Licenses for the Go stack: [`tui/README.md`](tui/README.md#licenses-verified-from-module-cache-license-files).

## AI use

See [`AI_USE.md`](AI_USE.md): what was written by the build agent vs the human developer,
and the runtime model (Gemma 4) that generates candidates inside the loop.

## Website

[`site/`](site/) — the project site (forge and fire, ore to metal). Static, deployed to
GitHub Pages via `.github/workflows/deploy-site.yml`. Results and the CLI reference are
generated from `evals/results.json` and `smelt --help` at build time, never hand-edited.
Libraries (with licenses): GSAP 3.13 (GreenSock No Charge), Space Grotesk / Inter /
JetBrains Mono (SIL OFL). Build locally: `python3 site/scripts/build.py`.

## License

MIT.
