# Furnace test fixtures

Slices of REAL smelt runs: `events.jsonl` + `state.json`, plus — for the
Result screen — `attempts/it<N>/{lib.rs,verify.json,bench.json}` and `source/`
copies of the Python target. Each fixture is a few KB at most.

**One deliberate test-only rewrite:** `state.json` → `target.path` is stored
run-RELATIVE (`source/<file>`) so teatest goldens render identically on every
machine (no absolute `/home/...` paths leak into goldens). Everything else is
verbatim, and every `source/` file matches the recorded
`target.source_sha256` exactly — the loader re-hashes it and renders a warning
instead of the compare columns on a mismatch.

| fixture | source run | provider · model | status | notes |
|---|---|---|---|---|
| `accepted-gemini/` | `runs/261011-015326-a41353` (L1 gate) | `gemini` · **`gemma-4-26b-a4b-it`** | accepted | 225/225 cases verified, 4.14x (lb 4.00x) — REAL Gemma run; it1 candidate + verify + bench; source `run_length.py` |
| `rejected-gemini/` | `evals/runs/linear_score/261011-020454-f5e8d0` | `gemini` · **`gemma-4-26b-a4b-it`** | rejected | 3 attempts (1.47x → 1.30x → 1.41x), all below the 1.5x threshold; last candidate it3 included; source `linear_score.py` |
| `refused-gemini/` | `runs/261011-033114-6d5f72` | `gemini` · **`gemma-4-26b-a4b-it`** | refused | purity refusal (`refused_impure`: target imports `random`). The refusal happens **before generation** — zero API calls at that stage; the label records the execution config the run was given. Source `impure_target.py` |
| `refused-hint-gemini/` | `runs/261011-054433-604a3c` | `gemini` · **`gemma-4-26b-a4b-it`** | refused | package-layout refusal (`refused_unsupported_target`) **with a refactor hint**; source `number.py` (humanize) |
| `mismatch-file/` | `runs/261011-054116-299276` | `file` · **— (no model)** | rejected | 3 verify mismatches on case `e0074` ("outcome kind differs: returned vs raised"); it1–it3 `verify.json` + it3 candidate; source `divide.py` |
| `missing-artifacts/` | `runs/261011-045519-892ab0` sliced | `local` · **`gemma-4-e2b-qat`** | accepted | real run with `attempts/` REMOVED to pin the missing-artifact rendering (clear message, never a crash); source `run_length.py` |
| `unit-file-provider/` | `runs/261011-024849-b4f411` (T0 golden run) | `file` · — | accepted | fast unit fixture with **no model involved**, labeled as such in the UI (`— (no model: file fixture)`) |

## Regenerating

Re-copy the artifacts from the source runs listed above (the table says which
files each fixture keeps). The events schema is pinned by smelt's
`tests/test_events_schema.py`; if the schema version changes, refresh these
fixtures and regenerate the teatest goldens (`go test ./internal/replay
-update`).
