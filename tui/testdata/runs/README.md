# Furnace test fixtures

Small slices of REAL smelt runs: only `events.jsonl` + `state.json`, copied
verbatim (~0.6–1.5 KB each). No oracle data, no candidate code, no transcripts.

| fixture | source run | provider | model | status | notes |
|---|---|---|---|---|---|
| `accepted-gemini/` | `runs/261011-015326-a41353` (L1 gate) | `gemini` | `gemma-4-26b-a4b-it` | accepted | 225/225 cases verified, 4.14x (lb 4.00x) — REAL Gemma run |
| `rejected-gemini/` | `evals/runs/linear_score/261011-020454-f5e8d0` | `gemini` | `gemma-4-26b-a4b-it` | rejected | 3 attempts (1.47x → 1.30x → 1.41x), all below the 1.5x threshold — REAL Gemma run |
| `refused-gemini/` | `runs/261011-033114-6d5f72` | `gemini` | `gemma-4-26b-a4b-it` | refused | purity refusal (`refused_impure`: target imports `random`). Honesty note: the refusal happens **before generation**, so zero API calls were made; the provider/model label records the execution config the run was given. |
| `unit-file-provider/` | `runs/261011-024849-b4f411` (T0 golden run) | `file` | — | accepted | fast unit fixture with **no model involved**, labeled as such in the UI (`— (no model: file fixture)`) |

## Regenerating

Re-copy `events.jsonl` + `state.json` from the source runs listed above. The
events schema is pinned by smelt's `tests/test_events_schema.py`; if the schema
version changes, refresh these fixtures and regenerate the teatest goldens
(`go test ./internal/replay -update`).
