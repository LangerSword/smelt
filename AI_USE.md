# AI use log (MLH disclosure)

This file records how AI was used to build smelt, and who reviewed what.

## Build-time AI (project creation)

- **Hermes Agent** (Nous Research build-agent session): wrote the initial scaffold,
  orchestrator, oracle capture/verify, scaffold templates, cargo build wrapper,
  sandboxed worker, benchmark protocol, providers, CLI, and report modules for
  v0.1-core — all within the event window (after 18:00 IST 2026-10-10).
- **Human developer**: wrote the build plan and phase gates, made all scope and
  funding decisions, and is the line-by-line reviewer for the modules marked below.

## Modules the developer reviews line-by-line (high-risk)

1. `oracle/capture.py` + `oracle/verify.py` — the acceptance oracle (freeze, hash,
   tamper check, comparison semantics).
2. `core/purity.py` — refusal rules.
3. `build/cargo.py` — static safety scan + build isolation.
4. `build/worker.py` — sandboxed execution (rlimits).
5. `bench/protocol.py` — timing protocol + anti-fake-speedup flags.
6. `core/orchestrator.py` — acceptance / refusal / retry decisions.

## Runtime AI (the product)

- A model (Gemma 4 — `gemma-4-e2b-qat` locally tonight; `gemma-4-31b-it` via API
  when funded) generates candidate Rust code. That is the product's core loop, not
  a build shortcut. Every generated candidate is verified by code before acceptance.

## Phase log

- **v0.1-core (L0)**: Hermes build agent wrote `core/`, `oracle/`, `scaffold/`, `build/`,
  `bench/`, `providers/`, `report.py`, `cli.py`, the demo target and the two fixture
  candidates inside the event window; the developer approved the plan and reviews the
  high-risk modules listed below line-by-line.
- **v0.2-cli (L1)**: Hermes build agent rewrote the provider layer (gemini / do /
  openai-compat / fake, with the retrying poster) and the CLI (capture, doctor,
  `--json`), and refactored the orchestrator for quiet/JSON runs + capture-only mode.
  Developer reviews the retry/backoff and secret-resolution code.

## Scope note

- No AI was used to write code before the event start; nothing was copied from
  prior projects or scratch experiments.
