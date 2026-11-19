# CLI reference

```
smelt run <file.py:fn> [--provider p] [--model m] [--candidate lib.rs] [--cases N]
                       [--max-attempts N] [--seed N] [--bench-min-ms MS]
                       [--repair | --no-repair] [--runs-dir D] [--json]
smelt capture <file.py:fn> [--cases N] [--json]      # freeze an oracle, no generation
smelt resume <run-dir> [--max-attempts N] [--repair | --no-repair] [--json]
smelt report <run-dir>                                # print the run report (markdown)
smelt scan <path> [--json]                            # candidates with tier + skip reasons
smelt apply <run-dir>                                 # VIEW ONLY diff + fallback shim
smelt doctor [--probe] [--json]                       # environment + provider checks
smelt evals [--provider p] [--model m] [--max-calls N] [--pause-s S] [--out-tag T]
            [--repair | --no-repair]
smelt furnace                                         # launch the Go TUI if installed
```

Bare `smelt` (no subcommand) launches the Furnace TUI.

## Provider / model defaults (v0.8)

`--provider` omitted → `SMELT_PROVIDER` env → first provider whose key exists
(nvidia, gemini, openai, do) → local. `--model` omitted → `SMELT_MODEL` →
`SMELT_<PROVIDER>_MODEL` → provider default (only nvidia/local ship one; the
rest require an explicit model). No model family is hardwired.

## Repair loop (v0.8)

`--repair` (default): attempt 2+ receives the previous candidate plus concrete
failure evidence — rustc stderr, safety-scan findings, failing oracle cases, or
the measured no-gain ratio. The acceptance gates never change. Evidence is
checkpointed to `attempts/itN/feedback.json` and reconstructed on `resume`.
`--no-repair` resends the identical base prompt (pre-v0.8 behavior).

## Exit codes

| code | meaning |
|---|---|
| 0 | accepted — verified, speedup clears the conservative 1.5x lower bound |
| 2 | config error (bad target, dotted qualname, missing required model) |
| 3 | refused — impure target, unsupported shape, or output outside the i64 domain (typed, with a hint) |
| 4 | rejected — no acceptable rewrite within budget (a correct, honest outcome) |
| 5 | harness/internal error (report the run dir) |

## Examples

```bash
# full loop, auto provider (resolves from your keys; e.g. NVIDIA_API_KEY)
smelt run examples/demo/run_length.py:rle_encode

# full loop, explicit provider + model
smelt run examples/demo/clamp_all.py:clamp_all --provider nvidia \
  --model moonshotai/kimi-k3.1-pro

# full loop, local model (offline)
smelt run examples/demo/run_length.py:rle_encode --provider local

# deterministic gate runs with hand-provided candidates (consumed in order)
smelt run examples/demo/run_length.py:rle_encode --provider fake \
  --candidate 'tests/fixtures/candidates/rle_encode_*.rs'

# what would change, without touching the repo
smelt apply runs/<id>
```

`--json` switches every command to a machine-readable summary (human progress
lines are suppressed). Every number in a report is labeled with the model that
produced it.
