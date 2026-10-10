"""Benchmark protocol: warmup, repeats, median, bootstrap CI, anti-fake-speedup flags.

House rules (reviewed closely by the developer):
- warmup runs are discarded; only measured runs feed the stats;
- medians + percentile-bootstrap 95% CI, deterministic seed;
- acceptance needs the CONSERVATIVE lower bound to clear 1.5x;
- >100x ratios are re-measured at 4x workload — a ratio that grows with size is
  flagged `suspicious_scaling` (algorithmic divergence, not honest speedup);
- sub-0.5 ms Rust medians are flagged `timer_limited` (timer noise, not speed).
"""

import random
import statistics

WARMUP = 3


def median_and_ci(samples: list[float], seed: int = 7, resamples: int = 2000,
                  conf: float = 0.95):
    xs = sorted(float(s) for s in samples)
    n = len(xs)
    med = statistics.median(xs)
    rnd = random.Random(seed)
    boots = []
    for _ in range(resamples):
        s = sorted(rnd.choices(xs, k=n))
        boots.append(statistics.median(s))
    boots.sort()
    lo = boots[int((1 - conf) / 2 * resamples)]
    hi = boots[int((1 + conf) / 2 * resamples) - 1]
    return med, lo, hi


def decide(ratio: float, ratio_ci_lo: float) -> str:
    """Acceptance rule: conservative ratio lower bound must clear 1.5x."""
    if ratio < 1.0:
        return "reject_regression"
    if ratio_ci_lo < 1.5:
        return "reject_no_meaningful_gain"
    return "accept"


def suspicious_scaling(ratio_base: float, ratio_scaled: float, factor: float = 6.0) -> bool:
    return ratio_scaled > ratio_base * factor


def timer_limited(rust_med: float, floor: float = 0.0005) -> bool:
    return rust_med < floor
