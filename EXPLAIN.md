# EXPLAIN — how every module works (for the developer, and for judges)

Written during the event; keep this current after every phase. One section per module:
what it does, why it exists, how it can fail. Plain words.

## core/orchestrator.py — the deterministic loop
Runs: purity probe → oracle capture (with the i64 domain guard) → attempts loop (generate → scan+build → verify) → bench → decide → report.
The model is only consulted inside `provider.generate()`; every other decision is code. Attempts are capped
(default 3); every stage writes `state.json` + `events.jsonl`, so `smelt resume` can continue a run.
Failures are typed exceptions → status refused/rejected/error. Exit codes: 0 accepted, 3 refused, 4 rejected, 5 error.
How it fails: provider outage → ProviderError (halts honestly); bad candidates → typed BuildError/VerifyMismatch.
**Repair loop (v0.8, default on, `--no-repair` to disable):** attempt 2+ receives the previous candidate plus
concrete failure evidence — rustc stderr, safety-scan findings, failing oracle cases (args/expected/got), or the
measured no-gain ratio. The gates never change; only the information the model gets does. Evidence is checkpointed
to `attempts/itN/feedback.json` (never into the event stream) and reconstructed on resume. `FileProvider` consumes
candidates in order across attempts (wraps when exhausted), so multi-candidate gate runs actually exercise attempt 2+.

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
v0.8: supported parameter types are str/int/float/bool/list[int]/list[float]/list[str]/tuple[int, int] (multi-parameter
targets combine them). **i64 domain guard:** if any recorded output leaves the i64 range (nested containers included),
the target is refused AT CAPTURE with a refactor hint — an i64 rewrite can never match it, and blaming the model via a
later verify_mismatch would be dishonest. The guard is a harness knob (`domain_guard=False`) only for the meta-eval's
divide battery, which deliberately straddles the domain edge to test the verifier on merits.

## oracle/verify.py — comparison semantics
Outcome parity (returned vs raised) + exact value equality (ints/str/bool/None exact; floats with rtol 1e-9;
NaN==NaN; lists element-wise). Documented limits: exception TYPE equality is not required (pyo3 maps errors
differently), and equivalence is only proven on the frozen inputs — that is the honest claim.
v0.8: **return-container fidelity** — tuples carry their own encoded tag, so a tuple and a list with identical
elements are NOT equal. Before this, a Vec-returning rewrite of a tuple-returning function passed verify (both
encoded as lists) and was only stopped by the speed threshold — a machine-dependent false-accept hole, closed
and gated by meta-eval candidate g02_list_not_tuple.

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
v0.8: **package-context loading (BUG-1 fix)** — targets inside packages are imported under their dotted package
name (walk up while `__init__.py` exists), so relative imports resolve exactly as in the real project; standalone
files keep the legacy loading path. **Bench on raising targets** — time_once/bench discard exceptions identically
on both sides (outcome parity was already proven in verify); previously any target that raised on an edge case
died as bench_insufficient. Tuple returns encode with a distinct `tuple` tag; `typing.Tuple` annotations normalize
to the builtin spelling.

## bench/protocol.py — honest timing
Warmup runs discarded; ≥7 measured reps; median + percentile-bootstrap 95% CI (seed 7). Acceptance requires the
CONSERVATIVE lower bound ≥ 1.5x. Flags: `suspicious_scaling` (ratios >100x re-checked at 4x workload) and
`timer_limited` (Rust median < 0.5 ms). Failure mode: a noisy machine widens the CI — the conservative bound
protects the claim.

## providers/providers.py — where candidates come from
Model-agnostic since v0.8 (the hardwired Gemma-4 defaults were removed). Providers behind one interface:
`nvidia` (NVIDIA NIM, OpenAI-compatible; default model picked empirically by `scripts/model_bakeoff.py`),
`gemini` (native REST, model required), `do` (DigitalOcean Inference, model required), `local` (llama.cpp /
any OpenAI-compatible server), `openai`/`openrouter` (any OpenAI-compatible endpoint, model required),
`file` (fixtures, consumed in order across attempts), `fake` (CI, no model involved).
Model resolution: `--model` → `SMELT_MODEL` → `SMELT_<PROVIDER>_MODEL` → provider default (only nvidia/local
ship one). Provider resolution when `--provider` is omitted: `SMELT_PROVIDER` → first provider whose key exists
(nvidia, gemini, openai, do) → local. Secrets resolve env → project `.env` → `~/.hermes/.env`, and are never logged.
All HTTP goes through one retrying poster (3 retries, exponential backoff + jitter, honors Retry-After on
429/5xx). The prompt embeds the Python source, the required Rust signature, the golden example, and semantic-fidelity
notes (floor-div vs truncating division, `%` sign, unicode code points, tuple-vs-list containers); the repair prompt
adds the previous candidate + failure evidence. Transcripts log model + usage only. Failure mode: HTTP errors →
ProviderError after retries.

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
Twenty-two hand-written WRONG rewrites across five batteries (rle_encode ×10, divide ×3,
manhattan tuple-arg ×3, rms list[float] ×3, sum_pair tuple-return ×3 — each broken differently,
each compiling). Every one must come back REJECTED on merits (exit 4, verify_mismatch) through the
full pipeline; any acceptance means the verifier has a false-accept bug and the script exits non-zero.
Pre-support refusals (exit 3) are reported as the RED state, not counted as verdicts — each widening
was observed RED before its support landed. The divide battery runs with the domain guard off (it
deliberately straddles the i64 edge). This is the miniature answer to "how do you know the oracle works?".

## scripts/model_bakeoff.py — empirical default selection (v0.8)
Runs a fixed mini-corpus (one str / one int / one list task) against each candidate NVIDIA model with
the shipping pipeline; ranks by accepted tasks → provider calls → median speedup lower bound. The
nvidia default model is the winner; the full labeled record is `evals/bakeoff-v08.json`.

## agent_api.py + mcp_server.py — the agent surfaces (v0.8)
One stdlib-only handler core (`agent_api.py`): ten verbs (scan / doctor /
capture / run / job / jobs / kill / verify / report / apply), errors as data,
CLI-driven (SMELT_BIN → PATH → uv run smelt). `smelt_run` is a DETACHED JOB:
the child lives in its own session with a log and a child-written exit code;
poll/tail/kill/verify are separate verbs, and verify checks artifact FRESHNESS
(mtime vs job start) plus terminal state — not just exit 0. Job children get an
allowlisted environment plus exactly the provider-key names smelt resolves;
foreign secrets never reach a job (dropped names recorded, values never).
`mcp_server.py` serves the same handlers over MCP stdio JSON-RPC (initialize
version negotiation, tools/list, tools/call; `smelt mcp`) — zero extra
dependencies, so any MCP-capable coding agent can drive smelt.

## plugin/ + .claude-plugin/ — packaged plugins (v0.8)
Hermes plugin (`plugin/`): plugin.yaml + register(ctx) wiring the ten tools
plus a pre_tool_call approval hook for the mutating verbs (run/capture/kill);
the handler core is vendored byte-identical and the skill is a synced copy
(scripts/sync_plugin.py, CI checks drift); plugin/smoke_load.py
proves the served surface without a Hermes install. Claude Code plugin (repo
root): .claude-plugin/plugin.json, /smelt-scan /smelt-run /smelt-report
commands, a PostToolUse hook that surfaces candidates after Python edits
(never runs anything unprompted), and .mcp.json. Every surface inherits the
same gates — no wrapper can accept what the core would reject.

## docs/events.md — the events contract (TUI input)
`events.jsonl` is the run's append-only stream; every record carries `schema_version`
(currently `2` — v0.8 added the `repair` event; schema-1 streams stay readable). The contract —
event table, per-event field sets, terminal verdicts — is documented in `docs/events.md`, pinned by
`tests/test_events_schema.py` (fingerprint + golden real-run fixture — now a real REPAIR run), and
regenerable via `scripts/schema_fingerprint.py`. The stream is what the Go TUI (Furnace) consumes;
the `node` field is reserved and the flow position is derived from the event type. Repair evidence
(failing cases, stderr, previous candidate) lives in `attempts/itN/feedback.json`, never in events.

## tui/ — Furnace (Go TUI, replay + live run + home)
A single Go binary (`tui/`, own go.mod). Replay mode renders a finished run from
`events.jsonl` (+ `state.json`): horizontal flow (derived from event types — the `node`
field is reserved), results panel, log pane, and the INGOT/SLAG/ASH verdict (COLD for a
killed run). Live mode (`furnace run`) spawns `smelt run --json` as a subprocess,
discovers the new run dir, tails its events.jsonl, shows attempts and a
"waiting for the model…" status, and kills the whole process group on quit (printing
the `smelt resume` command). The home screen (`furnace`, `app.go`) adds a prompt box
with slash commands, a scan picker fed by `smelt scan --json` (minimal T3 prerequisite
in the Python CLI), run history, and a view-only diff via `smelt apply`. The Python
core remains the source of truth; Furnace never runs generated code. Tests: 66 (unit +
teatest goldens over real-run fixtures, incl. a deterministic fake-smelt suite and the
required 80-column cases); build + vet + test run in CI. v0.8: provider defaults are
auto (the pickers list nvidia/gemini/local/do/openai/openrouter + (auto); the model
picker lists the bake-off candidates), header shows FURNACE v0.8, and the repair loop
is visible: ↻ evidence lines in the log, repair counts in the live panel/results box,
a ↻ marker per repaired attempt in the result strip (fixture: a real repair run).

## Generalization (merged state, v0.8)
Multi-parameter targets are supported: oracles use independent random columns per
parameter plus a capped edge product; keyword-only/variadic parameters are typed
refusals with hints. Rust panics become Python exceptions (worker catches
BaseException and records them — the process never aborts). `scan` classifies with
tiers (tier 1 supported / refused with reason) and statically resolves relative
imports against the package tree.

**Type domain (v0.8):** parameters str/int/float/bool/list[int]/list[float]/list[str]/
tuple[int, int]; returns str/int/float/bool/list[int]/list[float]/list[str]/tuple[int, int].
Tuple parameters use a worker-side coercion spec (JSON has no tuples; proven by an
`isinstance(p, tuple)` oracle target). Tuple RETURNS carry a distinct encoded tag —
a Vec-returning rewrite of a tuple-returning function is rejected on merits. Other
shapes (3+-tuples, mixed tuples, dicts, nested containers): typed refusals with hints.

**Package layouts (v0.8, BUG-1 fixed):** targets inside packages load in their package
context, so relative imports work; the blind-test refusal class "package layout" is
gone. Unresolvable relative imports and missing third-party deps remain typed refusals.

**i64 domain (v0.8 policy):** outputs beyond i64 are refused at capture with a hint
(previously: a misleading verify_mismatch after a wasted build). Inputs are generated
inside i64; big-int domains remain an open policy decision — never silently truncated.

## Furnace UX upgrade (branch `feature/furnace-ux`)
One screen, Hermes-style: persistent header, two-column main area at width ≥ 100
(loop flow + verdict + results | live panel with oracle progress bar, attempts,
speedup bar, last message), timestamped transcript with `✗`-labelled errors,
composer with slash-command autocomplete and prompt history, overlays (help,
provider/model/sessions pickers, view-only diff colouring), status line with
state/elapsed/verdict. `StartLive` now passes `--runs-dir` to the subprocess so
viewer and writer agree (regression test). Live gate at the time: real gemini run at
120×40 — INGOT, 3.05x lb 2.97x, 225/225 (historical, gemma-4 era). Events schema has
since moved to `2` (repair event, v0.8); schema-1 streams remain readable.

## v0.8 upgrade (merged state)
De-Gemma (model-agnostic providers + nvidia preset + auto resolution), repair loop
(evidence-fed attempts 2+, gates unchanged), package-context loading (BUG-1),
list[float] + tuple returns (meta-eval-first, RED observed before support),
return-container fidelity (tuple ≠ list), i64 domain guard at capture, bench on
raising targets, FileProvider cursor fix, semantic-fidelity prompt notes, events
schema 2, Furnace v0.8. Meta-eval: 22/22 wrong rewrites rejected on merits, 0 false
accepts. Every widening followed the same discipline: inject wrong rewrites FIRST,
observe the RED state, implement, re-run to GREEN.

## skills/smelt — the agent skill
SKILL.md (Agent Skills open standard; `agentskills validate ./skills/smelt` → exit 0) plus four
references — oracle format, benchmark protocol, failure taxonomy, provider config — and a thin CLI
wrapper script. The skill teaches any skills-compatible agent how to run smelt and what the refusal
and rejection outcomes mean; the logic stays in the package.

## cli.py — the interface
`smelt run | capture | resume | report | scan | apply | doctor | evals | furnace`; `--json` switches every
command to a machine-readable summary for CI (human progress lines are suppressed). Exit codes distinguish
accepted / refused / rejected / error so scripts react without parsing text. v0.8: `--provider` defaults to
auto-resolution from available keys; `--repair/--no-repair` controls the evidence feedback loop (default on);
`doctor` checks toolchain, sandbox worker, cargo target dir, local server, and provider keys (nvidia, gemini,
do, openai) plus the resolved default provider/model — green means no FAIL rows; `doctor --probe` also sends
tiny live calls where a key exists (catalog probes for OpenAI-compatible endpoints, a one-word generation
probe for gemini when SMELT_GEMINI_MODEL is set).
