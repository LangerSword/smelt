# How smelt works

smelt converts ONE slow, pure Python function into an equivalent Rust extension —
and only ships the result if code (never the model) proves equivalence and the
measured speedup clears a conservative threshold.

```
select ─▶ capture oracle ─▶ generate ─▶ build ─┬─ok─▶ verify ─┬─pass─▶ bench ─▶ accept ─▶ report
                          (model writes       │            │
                           lib.rs)            └─ errors ────┴─ mismatches ─▶ feed back ↺ (max N attempts)
                                                                             else reject (honest)
```

1. **Purity probe** — a static scan refuses I/O, randomness, time, globals,
   blocked calls. A refusal is a correct outcome (exit 3), with reasons and a
   refactor hint.
2. **Oracle capture** — the function is RUN on seeded random cases + a fixed
   edge battery; every input/output (or raised exception) is recorded, hashed,
   and made read-only. Multi-parameter targets use independent random columns
   per parameter plus a capped edge product. Nondeterminism and argument
   mutation are detected at capture time.
3. **Generation** — the model (Gemma 4 by default) writes `src/lib.rs` against a
   pinned scaffold (pyo3 =0.29.3, golden example embedded). Attempts are capped;
   build errors and verify mismatches are fed back.
4. **Safety scan** — every candidate is statically scanned before build: no
   `unsafe`, no extra crates, no build scripts, no net/fs/process, no `include_*!`.
5. **Verification** — the built extension runs every oracle case in a separate
   worker process. One mismatch rejects the attempt. Rust panics become Python
   exceptions (recorded, never aborting the process).
6. **Benchmark** — warmup + ≥7 repetitions, median + bootstrap 95% CI. Acceptance
   requires the CONSERVATIVE lower bound ≥ 1.5x. Anti-artifact flags
   (`suspicious_scaling`, `timer_limited`) guard against fake speedups.
7. **Report + checkpoints** — every attempt (including failures) lands in the run
   report; state is checkpointed (`state.json` + `events.jsonl`), so runs resume.

The claim, exactly: **no wrong rewrite is accepted on the tested inputs.**
The original Python function stays as the fallback. `smelt apply <run>` prints
the proposed change (view only) with a try/except shim — smelt never writes into
your project.

Known domain limits: integers are tested inside the i64 range; inputs whose
Python result exceeds i64 (e.g. `i64::MIN // -1`) cannot be matched by an i64
rewrite and are honestly rejected. Package layouts with relative imports are not
supported yet (typed refusal). See the FAQ for details.
