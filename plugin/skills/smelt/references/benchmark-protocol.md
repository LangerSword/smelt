# Benchmark protocol

Measured, not modeled. House rules (all enforced in code):

1. **Workload sizing.** The case set is repeated until the Python side takes at least
   `bench_min_ms` (default 100 ms) per repetition — sub-millisecond timings are noise.
2. **Warmup + reps.** 3 warmup repetitions are discarded; ≥7 measured repetitions feed
   the statistics.
3. **Medians + CI.** Python and Rust medians are reported with percentile-bootstrap
   95% confidence intervals (2000 resamples, deterministic seed).
4. **Acceptance rule.** Accept only when the CONSERVATIVE ratio lower bound
   (python CI low ÷ rust median) clears **1.5x**. Below 1.0x is a regression; 1.0–1.5x
   is "no meaningful gain" — both are honest rejections.
5. **Anti-artifact flags.**
   - `suspicious_scaling`: huge ratios (>100x) are re-measured at 4x workload; a ratio
     that grows with size indicates algorithmic divergence, not honest speedup.
   - `timer_limited`: a Rust median under 0.5 ms is flagged (timer noise range).
6. **Baseline honesty.** The Python side is the original function as written — if the
   benchmark is a strawman (e.g. a naive loop where numpy was available), say so in
   the report; smelt does not silently compare against a crippled baseline.

## Reporting rules

- Never round up: report the CI lower bound next to every headline speedup.
- Report every attempt, including failed ones — the report's attempt table is the
  contract.
- Numbers are always labeled with the model + provider that produced the candidate.
