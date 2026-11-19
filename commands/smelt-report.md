---
description: Show a smelt run's honest report (every attempt, measured speedup + CI)
argument-hint: <run-dir>
allowed-tools: Bash(smelt report:*), Bash(smelt apply:*)
---

Run `smelt report $ARGUMENTS` and present it without rounding up:

- Every attempt including failures, the benchmark medians + confidence
  intervals, flags (suspicious_scaling / timer_limited), and the outcome.
- Rejected and refused runs are correct results — present them as such.
- If the run was accepted, offer `smelt apply $ARGUMENTS` to view the diff +
  fallback shim (view only; the user applies changes by hand).
