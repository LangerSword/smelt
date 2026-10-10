# EXPLAIN — how every module works (for the developer, and for judges)

Written during the event; keep this current after every phase. One section per module:
what it does, why it exists, how it can fail. Plain words.

## core/orchestrator.py — the deterministic loop
Runs: purity probe → oracle capture → attempts loop (generate → scan+build → verify) → bench → decide → report.
The model is only consulted inside `provider.generate()`; every other decision is code. Attempts are capped
(default 3); every stage writes `state.json` + `events.jsonl`, so `smelt resume` can continue a run.
Failures are typed exceptions → status refused/rejected/error. Exit codes: 0 accepted, 3 refused, 4 rejected, 5 error.
How it fails: provider outage → ProviderError (halts honestly); bad candidates → typed BuildError/VerifyMismatch (fed to next attempt).

## core/state.py — checkpoint + event stream
`RunState` dataclass persisted as `state.json` (target hash, oracle hash, attempts, status); `EventLog` appends one
JSON record per transition to `events.jsonl` (CLI prints from it today; the TUI will subscribe later). sha256 helpers
hash files for tamper checks. Failure mode: none material — it is pure data.

## core/failures.py — typed failures
One class per outcome kind (`refused_impure`, `build_error`, `verify_mismatch`, …). Reports and tests switch on
`kind`, never on message text. Failure mode: an unmapped error becomes `internal_error` — still reported, never silent.

## core/purity.py — refusal rules
AST scan of the target: blocked imports (os, io, socket, subprocess, time, random, secrets, …), blocked calls
(open/input/eval/exec/compile), any global/nonlocal state. Conservative by design: refusing a pure function is
annoying, accepting an impure one is dangerous. Failure mode: too strict — the message lists every reason, so a
false refusal is easy to fix.

## oracle/capture.py — the ground truth
Generates 200+ cases (seeded random + fixed edge battery: empty string, repeats, long runs, unicode) and RUNS the
current Python function in the sandboxed worker to record answers — never trusting the spec. Re-runs 3 cases to
catch nondeterminism; checks argument mutation. Freezes `oracle.jsonl` + `meta.json` + `sha256` (files chmod 444).
`load_oracle` re-hashes and refuses to proceed on any mismatch. Failure mode: unsupported types → CaptureFailed with a clear note.

## oracle/verify.py — comparison semantics
Outcome parity (returned vs raised) + exact value equality (ints/str/bool/None exact; floats with rtol 1e-9;
NaN==NaN; lists element-wise). Documented limits: exception TYPE equality is not required (pyo3 maps errors
differently), and equivalence is only proven on the frozen inputs — that is the honest claim.

## scaffold/templates.py — pinned scaffold
`Cargo.toml` (pyo3 `=0.29.3`, cdylib, crate `smelt_ext`) + a golden compiling `lib.rs`. The model never writes
Cargo.toml; it fills in one function body only. This is the designed fix for the #1 observed failure (pyo3 API drift).

## build/cargo.py — safety scan + build
Static scan refuses: `unsafe`, std net/process/fs, `include_*!`, `env!`, `Command`, `extern crate`, `libc`, >200KB,
and missing function/module glue. Then `cargo build --release` in the attempt's scratch dir with a dedicated
`CARGO_TARGET_DIR` and `PYO3_PYTHON`. Failure mode: scanner false-positives (pattern list is explicit and reviewable);
a refused candidate is saved under `_rejected/` for inspection.

## build/worker.py — sandboxed execution
One JSON request in, one JSON out. Sets RLIMIT_AS (1 GiB) + RLIMIT_CPU (180 s). Loads the Python target or the
generated `.so` and runs cases; target stdout is swallowed so it can never corrupt the protocol. Failure mode: any
crash → typed worker error to the parent — never a silent wrong result.

## bench/protocol.py — honest timing
Warmup runs discarded; ≥7 measured reps; median + percentile-bootstrap 95% CI (seed 7). Acceptance requires the
CONSERVATIVE lower bound ≥ 1.5x. Flags: `suspicious_scaling` (ratios >100x re-checked at 4x workload) and
`timer_limited` (Rust median < 0.5 ms). Failure mode: a noisy machine widens the CI — the conservative bound
protects the claim.

## providers/providers.py — where candidates come from
Six providers behind one interface: `gemini` (native REST, default `gemma-4-26b-a4b-it`), `do` (DigitalOcean Inference,
OpenAI-compatible), `local` (llama.cpp), `openai` (any OpenAI-compatible endpoint), `file` (fixtures),
`fake` (CI, no model involved). Secrets resolve env → project `.env` → `~/.hermes/.env`, and are never logged.
All HTTP goes through one retrying poster (3 retries, exponential backoff + jitter, honors Retry-After on
429/5xx). The prompt embeds the Python source, the required Rust signature, and the golden example; transcripts
log model + usage only. Failure mode: HTTP errors → ProviderError after retries.

## worker_client.py — parent side of the sandbox
Spawns the worker with the run's Python, feeds the JSON request, parses the JSON response. Non-zero exit or
unparsable output → typed VerifyCrash.

## report.py — the honest report
Markdown table of EVERY attempt (including failures), benchmark medians + CI + flags, and the outcome line:
accepted / rejected / refused. Nothing is rounded up. This is what goes into submissions.

## evals.py — the eval runner
Runs the frozen corpus (`evals/corpus/<category>/<fn>.py`), strictly sequentially, full pipeline per
function. Between tasks it pauses (rate-limit courtesy); a global provider-call cap stops the run early and
records the rest as skipped — never silently dropped. Writes `evals/results.json` + `evals/results.md`
(generated, never hand-edited) including failures, refusals, rejections, flags and exact provider-call
counts. `--out-tag` produces extra runs (e.g. a second model) without overwriting the primary results.

## scripts/meta_eval.py — the false-accept gate
Ten hand-written WRONG rewrites of the demo function (each broken differently, each compiling). Every one
must come back REJECTED (exit 4) through the full pipeline; any acceptance means the verifier has a
false-accept bug and the script exits non-zero. This is the miniature answer to "how do you know the
oracle works?".

## docs/events.md — the events contract (TUI input)
`events.jsonl` is the run's append-only stream; every record now carries `schema_version`
(currently `1`). The contract — event table, per-event field sets, terminal verdicts — is
documented in `docs/events.md`, pinned by `tests/test_events_schema.py` (fingerprint +
golden real-run fixture), and regenerable via `scripts/schema_fingerprint.py`. The stream
is what the Go TUI (Furnace) consumes; the `node` field is reserved and the flow position
is derived from the event type.

## tui/ — Furnace (Go TUI, read-only replay)
A single Go binary (`tui/`, own go.mod) that renders a finished run from `events.jsonl`
(+ `state.json`): horizontal flow (derived from event types — the `node` field is
reserved), results panel, log pane, and the INGOT/SLAG/ASH verdict (COLD for a killed
run). The Python core remains the source of truth; Furnace never runs generated code.
Tests: unit + teatest goldens (full-frame, via the same golden mechanism teatest uses)
over real-run fixtures — three REAL Gemini runs (accepted/rejected/refused) plus a
file-provider unit fixture — including the required 80-column case. Live `furnace run`
is T2; the interactive home screen is T3.

## skills/smelt — the agent skill
SKILL.md (Agent Skills open standard; `agentskills validate ./skills/smelt` → exit 0) plus four
references — oracle format, benchmark protocol, failure taxonomy, provider config — and a thin CLI
wrapper script. The skill teaches any skills-compatible agent how to run smelt and what the refusal
and rejection outcomes mean; the logic stays in the package.

## cli.py — the interface
`smelt run | capture | resume | report | doctor`; `--json` switches every command to a machine-readable
summary for CI (human progress lines are suppressed). Exit codes distinguish accepted / refused / rejected /
error so scripts react without parsing text. `doctor` checks toolchain, sandbox worker, cargo target dir, local
server, and provider keys — green means no FAIL rows; `doctor --probe` also sends tiny live calls where a key
exists (a depleted Gemini key reports HTTP 402 honestly).
