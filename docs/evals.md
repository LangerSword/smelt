# Evals

Three evidence layers, all reproducible, all with failures shown:

1. **Corpus** (`evals/results.md`, generated — never hand-edited) — 24 fresh
   single-parameter functions run sequentially with a global provider-call cap.
   Latest: **20 accepted / 4 honest rejections / 0 errors** on
   `gemma-4-26b-a4b-it` (36 calls, no 429s); median accepted speedup 2.83x.
   A local-model arm (`gemma-4-e2b-qat` via llama.cpp) is in
   `evals/results-local.md`: 18/24 accepted, fully offline.
2. **Meta-eval** (`scripts/meta_eval.py`) — hand-written KNOWN-WRONG rewrites
   must all be rejected. Two batteries, **13/13 rejected, unexpected_accepted=0**:
   ten `rle_encode` rewrites + the multi-parameter battery for `divide`
   (wrong value / wrong exception / panic-where-Python-returns). Run it:
   `python scripts/meta_eval.py --cases 60` → `META_EXIT=0`.
3. **Blind generalization test** (`evals/general.md`, generated) — 3 real
   open-source repos / 10 functions, list frozen BEFORE any run (sha256 in
   `evals/general_freeze_proof.txt`, unchanged across re-runs — no tuning).
   Before the fixes: 3 refused / 7 errors (six with a misleading message).
   After: **9 refused / 1 config error / 0 errors, every message carrying the
   real cause and a refactor hint; 0 provider calls; 0 crashes** — the list is
   honestly non-convertible today (package layouts / unsupported shapes /
   impurity), so it measures classification quality, not conversion.

Also: `tests/` (pytest, 26 tests incl. typed-refusal and multi-param suites),
the Go TUI suite (26 tests, teatest goldens over REAL run fixtures), and CI
(Python + Go jobs) on every push.
