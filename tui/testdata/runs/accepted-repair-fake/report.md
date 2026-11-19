# smelt run report — 261119-025423-4c8849

- target: `/home/lakshaya/projects/smelt/examples/demo/run_length.py:rle_encode` (sha256 `62cd19ed8285…`)
- provider: `fake` · model: `—` · ran on: laptop
- oracle: 85 frozen cases, hash `813804c805d4…`

## Attempts

| # | source | build | verify | bench | outcome |
|---|--------|-------|--------|-------|---------|
| 1 | fake | ok | mismatch 70/85 | - | verify_mismatch: r0000 output differs |
| 2 | fake | ok | pass 85/85 | 2.57x (lb 2.54x) | ACCEPTED |

## Benchmark (measured, not modeled)

- python median 39.12 ms (CI 38.67–40.42 ms)
- rust   median 15.19 ms (CI 14.90–16.83 ms)
- speedup: **2.57x** (conservative lower bound 2.54x)
- workload: 20400 calls/rep · 10 reps (first 3 discarded) · 4x-scaling ratio 2.31x
- flags: none

## Outcome

**accepted** — verified 85/85 cases; speedup 2.57x (conservative lower bound 2.54x)

Honesty note: rejected and refused runs are correct results; nothing here is rounded up.
