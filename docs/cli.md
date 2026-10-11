# CLI reference

```
smelt run <file.py:fn> [--provider p] [--model m] [--candidate lib.rs] [--cases N] [--json]
smelt capture <file.py:fn> [--cases N] [--json]      # freeze an oracle, no generation
smelt resume <run-dir> [--json]                       # continue an interrupted run
smelt report <run-dir>                                # print the run report (markdown)
smelt scan <path> [--json]                            # candidates with tier + skip reasons
smelt apply <run-dir>                                 # VIEW ONLY diff + fallback shim
smelt doctor [--probe] [--json]                       # environment + provider checks
smelt evals [--provider p] [--model m] [--max-calls N] [--pause-s S] [--out-tag T]
smelt furnace                                         # launch the Go TUI if installed
```

## Exit codes

| code | meaning |
|---|---|
| 0 | accepted — verified, speedup clears the conservative 1.5x lower bound |
| 2 | config error (bad target, dotted qualname, unsupported annotation on a required path) |
| 3 | refused — impure target or unsupported-but-understood shape (typed, with a hint) |
| 4 | rejected — no acceptable rewrite within budget (a correct, honest outcome) |
| 5 | harness/internal error (report the run dir) |

## Examples

```bash
# full loop, local model (offline)
smelt run examples/demo/run_length.py:rle_encode --provider local

# full loop, Gemma 4 via the Gemini API (default model gemma-4-26b-a4b-it)
smelt run examples/demo/clamp_all.py:clamp_all --provider gemini

# deterministic gate runs with a hand-provided candidate
smelt run examples/demo/divide.py:divide --provider file \
  --candidate tests/fixtures/candidates/divide_correct.rs

# what would change, without touching the repo
smelt apply runs/<id>
```

`--json` switches every command to a machine-readable summary (human progress
lines are suppressed). Every number in a report is labeled with the model that
produced it.
