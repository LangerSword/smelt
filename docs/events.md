# events.jsonl contract

The events stream is Furnace's only observable stream. `smelt` writes one JSON
object per line, append-only, newest last. `furnace` (the Go TUI) reads it as
the source of truth for run state; the Python core never depends on Furnace.

## Versioning

Every record carries `schema_version` — a string. The current value is `1`
(matching `EVENT_SCHEMA_VERSION` in `src/smelt_rs/core/state.py`). Adding a
field is a non-breaking change; removing, renaming, or retyping a field is a
breaking change and requires bumping the constant. `tests/test_events_schema.py`
fails on any emitter change until the version is bumped AND the fingerprint
(`tests/fixtures/events/schema_fingerprint.json`) is regenerated with
`python scripts/schema_fingerprint.py --write`.

Missing `schema_version` means pre-1 output; treat those records as legacy and
mark them in Furnace status lists.

## Record shape (common fields)

```json
{"ts": 1791667129.5195718, "schema_version": "1", "event": "purity_ok", "node": ""}
```

- `ts` — float seconds, wall clock (`time.time()`).
- `schema_version` — string. See above.
- `event` — one of the types in the table below.
- `node` — RESERVED. The current emitter always writes `""`; Furnace derives the
  flow position from the event type instead (mapping table below).
- Additional fields are event-specific (listed per type).

## Furnace flow (derived from the event type, in order)

`select` → `oracle` → `generate` → `build` → `verify` → `bench` → `verdict`.
Furnace renders these as a horizontal flow; each event advances the flow.

## Event types

| Event | Furnace flow | Extra fields | Terminal? | Meaning |
|---|---|---|---|---|
| `run_start` | — | `target` (str `path:func`), `provider` (str), `model` (str) | no | Run created; engine up |
| `purity_ok` | select | — | no | Purity probe passed; target accepted |
| `capture_done` | oracle | `n_cases` (int), `sha256` (str, first 16 hex chars) | no | Oracle frozen (full hash in `runs/<id>/oracle/sha256`) |
| `attempt_start` | generate | `attempt` (int, 1-based) | no | A fresh generation attempt begins |
| `resume` | generate | `from_attempt` (int) | no | Run resumed; the loop continues at attempt `from_attempt` |
| `safety_violation` | generate | `attempt` | no | Candidate failed the static scan — attempt continues |
| `build_error` | build | `attempt`, `subkind` (str: `api_drift`\|`compile_error`\|`network`\|`missing_artifact`) | no | Cargo build failed |
| `verify_mismatch` | verify | `attempt`, `n_bad` (int) | no | Built extension disagreed with the oracle on at least one case |
| `accept` | verdict | `ratio` (float), `ratio_ci_lo` (float), `flags` (list; may contain `suspicious_scaling`, `timer_limited`) | yes (accepted) | Verified & speedup clears the conservative 1.5x lower bound |
| `reject_no_meaningful_gain` | verdict | `ratio` (float) | yes (rejected) | Correct rewrite but below the 1.5x threshold |
| `halt` | — | `kind` (str, failure kind), `message` (str) | yes (refused/error) | Run stopped — purity refusal, provider failure, internal error, … |
| `run_end` | verdict | `status` (str: `accepted`\|`rejected`\|`refused`\|`error`), `reason` (str) | yes | Final line — once per completed run stream |

## Terminal verdict

Furnace maps `run_end.status`:
- `accepted` → **INGOT**
- `rejected` → **SLAG**
- `refused` / `error` → **ASH**

No other status is defined.

## Examples — real lines (verbatim)

Copied from `runs/261011-024849-b4f411/events.jsonl` — a real accepted run
(provider `file`, no model involved; 85/85 cases verified, 3.28x lower bound
3.25x). The same stream is the test fixture `tests/fixtures/events/golden_run.jsonl`.

```json
{"ts": 1791667129.5195718, "schema_version": "1", "event": "run_start", "node": "", "target": "/home/lakshaya/projects/smelt/examples/demo/run_length.py:rle_encode", "provider": "file", "model": "-"}
{"ts": 1791667129.519995, "schema_version": "1", "event": "purity_ok", "node": ""}
{"ts": 1791667129.5949135, "schema_version": "1", "event": "capture_done", "node": "", "n_cases": 85, "sha256": "033b13d605ac44a7"}
{"ts": 1791667129.5954425, "schema_version": "1", "event": "attempt_start", "node": "", "attempt": 1}
{"ts": 1791667134.8142703, "schema_version": "1", "event": "accept", "node": "", "ratio": 3.27883864270321, "ratio_ci_lo": 3.2458072733424155, "flags": []}
{"ts": 1791667134.8144522, "schema_version": "1", "event": "run_end", "node": "", "status": "accepted", "reason": "verified 85/85 cases; speedup 3.28x (conservative lower bound 3.25x)"}
```

## Invariants

1. Exactly one `run_start` (first line) and one `run_end` (last line, if the stream is
   complete). A stream missing `run_end` means the run was killed mid-flight.
2. `schema_version` is present on every record.
3. `capture_done.sha256` is the first 16 hex chars of the frozen oracle hash; the full
   hash lives in `runs/<id>/oracle/sha256`.
4. A new attempt is always preceded by `attempt_start`; feedback loops emit a new
   `attempt_start`. Furnace shows the latest attempt with a counter.
5. Nothing in events ever contains a secret: no API key, no candidate Rust source
   text, no token — only sizes and metadata. Mismatch events carry counts (`n_bad`),
   never the offending values.

## Implementation (Python side)

- Emitter: `src/smelt_rs/core/state.py`, class `EventLog.emit`; constant `EVENT_SCHEMA_VERSION`.
- Schema tests: `tests/test_events_schema.py`; fingerprint tool: `scripts/schema_fingerprint.py`.
- Golden fixture: `tests/fixtures/events/golden_run.jsonl` (a real run's stream, verbatim).
- Consumer status: Furnace (`feature/furnace` branch) is the first consumer; `smelt`'s
  own resume logic is unaffected by the added field.
