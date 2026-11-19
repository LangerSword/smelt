# Failure taxonomy

Every failure is typed (`kind`), reported in the run report, and mapped to an exit code.
None of them is a crash; `refused` and `rejected` are CORRECT outcomes.

| kind | exit | meaning |
|---|---|---|
| `refused_impure` | 3 | Purity probe found I/O, randomness, time, globals, or blocked calls. Reasons listed. |
| `capture_failed` | 5 | Oracle capture failed (unsupported type, nondeterminism, argument mutation, worker error). |
| `oracle_tampered` | 5 | Frozen oracle hash mismatch — files changed after freeze. Run aborted. |
| `target_changed` | 5 | Target file hash changed since checkpoint; resume refused. |
| `safety_violation` | — | Candidate scanned as unsafe (unsafe/extra crates/net/fs/process/build script). Attempt continues. |
| `build_error[subkind]` | — | cargo failed: `api_drift` (pyo3 API mismatch), `compile_error`, `network`, `missing_artifact`. Attempt continues. |
| `verify_mismatch` | — | Built extension produced different output on ≥1 oracle case. Sample included. Attempt continues. |
| `verify_crash` | — | Worker or extension crashed during verification. Attempt continues. |
| `bench_insufficient` | — | Timing could not be measured reliably. Attempt continues. |
| `bench_regression` / `reject_no_meaningful_gain` | 4 | Correct but slower / below the 1.5x conservative threshold. Final rejection after budget. |
| `budget_exhausted` | 4/5 | Attempt cap or provider candidates exhausted. |
| `provider_error` | 5 | Model provider failed after retries (e.g. HTTP 402/403/503). Nothing accepted. |
| `config_error` | 2 | Bad target spec, unsupported parameter/return type for this build. |

Rules: an attempt that fails at any stage is recorded and the loop continues until the
attempt budget; the final status is whatever the last honest outcome was. A wrong-but-
plausible rewrite NEVER passes: verification is all-or-nothing (0 mismatches required).
