---
name: smelt
description: Convert ONE slow pure Python function into an equivalent pyo3 Rust extension, verified by a frozen differential oracle — code, not the model, checks equivalence and measures the real speedup. Use when a single Python function (not the whole project) is too slow, when asked to "make this function faster", "port this function to Rust", or "optimize this hot path with proof". Refuses impure functions; rejects rewrites with no real speedup; never accepts a wrong rewrite on the tested inputs. Do not use for whole-project ports, impure functions (I/O, globals, randomness), functions with no runnable inputs, or machines without a Rust toolchain.
license: MIT
compatibility: Requires Python 3.11+, Rust (cargo, rustc) and crates.io access for the first build. Model calls need either a Gemini API key (GEMINI_API_KEY, falls back to GOOGLE_API_KEY) or any OpenAI-compatible server (llama.cpp locally). The verify and benchmark steps need no network.
metadata:
  author: LangerSword
  homepage: https://github.com/LangerSword/smelt
  version: "0.4"
---

# smelt — verified Python→Rust hotspot conversion

smelt takes ONE slow, pure Python function and freezes what it actually does into a
differential oracle (200+ recorded input/output cases, hashed and read-only). A model
(Gemma 4) writes an equivalent Rust extension (`pyo3`). **Code, not the model, checks
that the Rust answers identically on every recorded case.** Only then does smelt
benchmark both sides and report the measured speedup with a confidence interval.
Anything that fails the oracle or shows no real gain is rejected. The original Python
function stays as the fallback.

The honest claim: *no wrong rewrite is accepted on the tested inputs.*

## When to use

- One identified hot function in an otherwise working Python codebase.
- The user asks to "make this faster", "port this to Rust", "verify a rewrite".
- A measured, CI-checkable speedup with proof is wanted (not just plausible code).

## When NOT to use

- Whole-project ports or multi-function sweeps (one function per run, by design).
- Impure targets: I/O, global state, randomness, time dependence — smelt refuses
  these by a static purity probe, and the refusal is a correct outcome.
- Functions whose inputs cannot be generated or supplied (no runnable cases).
- Machines without cargo/rustc that cannot install a Rust toolchain.

## Workflow

1. **Doctor first.** `smelt doctor` — verifies Python, cargo, rustc, the sandbox
   worker, the cargo target cache, the local model server, and provider keys.
2. **Check the target is pure.** The purity probe scans for blocked imports
   (`os`, `socket`, `time`, `random`, …), blocked calls (`open`, `eval`, …) and
   global/nonlocal state. Impure targets are refused with the reasons listed.
3. **Run:** `smelt run path/to/file.py:function --provider gemini --model gemma-4-26b-a4b-it`
   - Oracle capture: generated seeded cases + a fixed edge battery (empty, repeats,
     long runs, unicode), recorded by RUNNING the current function.
   - Generation attempts (max 3): the model writes `src/lib.rs`, which must compile
     against smelt's pinned scaffold (pyo3 =0.29.3, golden example embedded in the
     prompt — this is the fix for API drift).
   - Safety scan of every candidate before build: no `unsafe`, no extra crates, no
     build scripts, no `std::net`/`std::process`/`std::fs`, no `include_*!`/`env!`.
   - Verify: the built extension runs every oracle case in a sandboxed worker.
   - Benchmark: warmup + ≥7 measured reps; median + bootstrap 95% CI; acceptance
     requires the CONSERVATIVE lower bound ≥ 1.5x. Flags: `suspicious_scaling`
     (ratios >100x re-checked at 4x workload), `timer_limited` (<0.5 ms Rust median).
4. **Read the report.** `smelt report runs/<id>` — every attempt including failures,
   the measured table, flags, and the outcome (accepted / rejected / refused).
5. **Resume or capture-only:** `smelt resume runs/<id>` continues an interrupted run
   after re-validating the oracle and target hashes; `smelt capture path.py:fn` freezes
   an oracle without any generation.

## Exit codes (scriptable)

| code | meaning |
|---|---|
| 0 | accepted — verified, speedup ≥ conservative 1.5x |
| 3 | refused — impure target (a correct, explicit outcome) |
| 4 | rejected — no acceptable rewrite within budget (also correct) |
| 5 | harness/internal error (report the run dir) |
| 2 | configuration error (bad target, unsupported type) |

## Safety rules

- Generated Rust is untrusted: builds happen in run-scratch dirs, execution in a
  separate worker process with resource limits; smelt never writes into your project.
- Secrets resolve env → project `.env` → `~/.hermes/.env` and are never logged;
  transcripts record model + sizes + usage only.
- Out-of-domain inputs: integers are tested inside the 64-bit range; big Python ints
  are outside the tested domain and are never silently truncated (documented in README).

## References

- `references/oracle-format.md` — oracle files, hashing, tamper rules, edge battery.
- `references/benchmark-protocol.md` — timing protocol and anti-artifact flags.
- `references/failure-taxonomy.md` — every typed failure kind and what it means.
- `references/provider-config.md` — providers, environment variables, retries.
- `scripts/run_smelt.sh` — thin wrapper that forwards to the installed `smelt` CLI.
