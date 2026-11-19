# Evals

Three evidence layers, all reproducible, all with failures shown:

1. **Corpus** (`evals/results.md`, generated — never hand-edited) — 24 fresh
   single-parameter functions run sequentially with a global provider-call cap
   and a per-task wall-clock cap (NIM stalls record as `timeout`). v0.8 run:
   provider `nvidia`, model picked by the bake-off (`evals/bakeoff-v08.json`),
   repair loop on. Historical Gemma-4 arms (kept verbatim, labeled):
   `evals/results-gemma.md` — 20/24 accepted (36 calls, median 2.83x) and
   `evals/results-after.md` — 23/24 (27 calls, median 2.72x), both on
   `gemma-4-26b-a4b-it`; local arm `evals/results-local.md`
   (`gemma-4-e2b-qat` via llama.cpp): 18/24 accepted, fully offline.
2. **Meta-eval** (`scripts/meta_eval.py`) — hand-written KNOWN-WRONG rewrites
   must all be rejected ON MERITS (exit 4, verify_mismatch). Five batteries,
   **22/22 rejected, unexpected_accepted=0** (v0.8): ten `rle_encode` rewrites,
   the multi-parameter `divide` battery (wrong value / wrong exception /
   panic-where-Python-returns; domain guard off — it deliberately straddles the
   i64 edge), the tuple-arg `manhattan` battery, the `list[float]` `rms` battery,
   and the tuple-RETURN `sum_pair` battery (swapped elements / list-not-tuple /
   wrong second element). Each widening was observed RED (refusals, or a
   verify-passing wrong-type candidate) before its support landed. Run it:
   `python scripts/meta_eval.py --cases 60` → exit 0.
3. **Blind generalization test** (`evals/general.md`, generated) — 3 real
   open-source repos / 10 functions, list frozen BEFORE any run (sha256 in
   `evals/general_freeze_proof.txt`, unchanged across re-runs — no tuning).
   Before the fixes: 3 refused / 7 errors (six with a misleading message).
   After: **0 accepted, 9 refused, 1 config error, 0 errors, 0 provider calls** —
   refusals: 6 package layouts (relative imports), 2 impurity, 1 unsupported type;
   the config error is a dotted qualname (exit 2). Every message carries the real
   cause and a refactor hint; nothing crashed. **This shows safety, not
   generality** — the list is honestly non-convertible today (package layouts /
   unsupported shapes / impurity), so it measures classification quality, not
   conversion.

Also: `tests/` (pytest — typed refusals, multi-param, tuples, repair loop,
package loading, float lists, tuple returns, domain guard, providers), the Go
TUI suite (58 tests, teatest goldens over REAL run fixtures), and CI
(Python + Go jobs) on every push.
