# smelt

**Smelt a slow pure Python function into a verified Rust extension. Only proven metal ships.**

smelt takes ONE slow, pure Python function and freezes what it actually does into a
differential oracle — 200+ recorded input/output cases, hashed and read-only. A model
(Gemma 4) writes an equivalent Rust extension (`pyo3`). **Code, not the model, checks
that the Rust answers identically on every recorded case.** Only then does smelt time
both implementations and report the measured speedup, with a confidence interval.
Anything that fails the oracle is rejected. The original Python function stays on as
the fallback.

The honest claim: **no wrong rewrite is accepted on the tested inputs.**

smelt is a metalworking metaphor, not a networking tool.

> Status: built live at **sudo Hacktober** (MLH, SRM AP Amaravati), Oct 10–11 2026,
> solo. Results table lands at v0.3-evals; this README is the submission surface.

## How it works

```
select ─▶ capture oracle ─▶ generate ─▶ build ─┬─ok─▶ verify ─┬─pass─▶ bench ─▶ accept ─▶ report
                          (model writes       │            │
                           lib.rs)            └─ errors ────┴─ mismatches ─▶ feed back ↺ (max 3 attempts)
                                                                             else reject (honest)
```

The orchestrator is deterministic; the model only acts inside `generate`. Every state
transition is checkpointed to `runs/<id>/state.json` + `events.jsonl`, so runs resume.

## Quickstart

```bash
smelt run examples/demo/run_length.py:rle_encode --provider local
smelt run examples/demo/run_length.py:rle_encode --provider file \
      --candidate tests/fixtures/candidates/rle_encode_correct.rs
smelt resume runs/<run-id>
smelt report runs/<run-id>
```

Requires Python 3.11+, Rust (`cargo`), and (for model runs) a provider. The verify and
benchmark steps need no network.

## Safety (generated Rust is untrusted)

- Crate scaffold and `Cargo.toml` are pinned (pyo3 `=0.29.3`) and supplied by smelt —
  the model fills in one function body only.
- Static scan before build rejects: `unsafe`, extra crates, `build.rs`, std
  net/process/fs, `include_*!`, `env!`.
- Build and execution happen in run-scratch directories; the extension runs in a
  separate worker process with resource limits.
- smelt never writes into your project — it emits a report (PR output lands at L5).

## Providers

| Provider | Status |
|---|---|
| `local` — llama.cpp OpenAI-compatible server (Gemma 4 E2B gguf) | working |
| `file` — hand-provided candidate (fixtures, gate checks) | working |
| Google AI Studio `gemma-4-31b-it` | planned (key needs credits) |
| DigitalOcean Inference `gemma-4-31B-it` | planned (MLH credits) |

Every number in results is labeled with the exact model + provider that produced it.

## License

MIT. Third-party libraries + licenses are listed at v0.3-evals.
