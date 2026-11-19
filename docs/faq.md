# FAQ

**Is this a thin wrapper around a model?**
No — the model only writes candidate text. Acceptance, refusal, retries,
verification and benchmarking are code. The model never decides anything.

**Why was my function rejected (exit 4)?**
Rejection means: correct rewrite not found within the attempt budget, or the
measured speedup did not clear the conservative 1.5x lower bound. That is an
honest outcome, not an error. Small functions legitimately fail to beat pyo3
call overhead.

**Why was my function refused (exit 3)?**
The target is impure (I/O, randomness, time, globals), an unsupported shape
(keyword-only/variadic parameters, unsupported types), has an unresolvable
import, or its recorded outputs leave the i64 domain (v0.8 domain guard). The
message names the reason and a refactor hint.

**My function is in a package — does that work?**
Yes (v0.8): targets load in their package context, so relative imports resolve
as in the real project. "could not load the target module" now means a real
import failure — a missing third-party dependency (install it into the smelt
environment) or a broken import in the package.

**What's the i64 domain gap?**
Integers are tested inside the i64 range. Since v0.8, targets whose recorded
outputs exceed i64 (e.g. `i64::MIN // -1`, or a product of two extreme values)
are refused AT CAPTURE with a hint — no wasted model calls, no misleading
mismatch. Big-int support remains an open policy decision; nothing is silently
truncated.

**Are tuples supported?**
Yes: `tuple[int, int]` parameters (any number of positional params) and, since
v0.8, `tuple[int, int]` returns — with true container fidelity: a rewrite
returning a list where Python returns a tuple is rejected on merits. Other
tuple shapes (3+, mixed) are typed refusals with a hint. JSON has no tuples —
a per-parameter coercion spec converts 2-element lists back before every call,
so the target sees the same value the annotation promises.

**Does it use Gemma?**
Not anymore — v0.8 removed the hardwired Gemma-4 defaults. smelt is
model-agnostic: `nvidia` (NVIDIA NIM), `gemini` (any served model), `local`
(llama.cpp, fully offline), `do`, `openai`/`openrouter`, or hand-provided
candidates (`file`/`fake`). Pre-v0.8 results in `evals/` were produced by
Gemma-4 models and stay labeled with them.

**Can I run it with no network?**
`capture`, `verify`, `bench` and `--provider local`/`file` need no network.

**What does `smelt apply` do?**
Prints the proposed change (new-file diff + build command + try/except shim).
View only — it never writes into your repository.

**Where do the numbers come from?**
Every table in this repo is generated from real run output; each number is
labeled with the model that produced it. Nothing is rounded up; failures stay
in the tables.
