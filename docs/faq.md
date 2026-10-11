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
The target is impure (I/O, randomness, time, globals) or an unsupported shape
(keyword-only/variadic parameters, unsupported types, package layouts with
relative imports). The message names the reason and a refactor hint.

**My function is in a package — why "could not load the target module"?**
Package layouts (relative imports) are not supported yet; point smelt at a
standalone module or copy the target file out of the package.

**What's the i64 domain gap?**
Integers are tested inside the i64 range. Inputs whose Python result exceeds
i64 (e.g. `i64::MIN // -1`, or a product of two extreme values) cannot be
matched by an i64 rewrite — candidates are honestly rejected on those edges.
The domain-policy decision (e.g. filtering such cases at capture time) is open.

**Are tuples supported?**
`tuple[int, int]` parameters are implemented on `feature/general` (unmerged at
the developer's 06:50 hard limit; meta-eval 16/16 there). Other tuple shapes and
tuple returns are typed refusals with a hint. JSON has no tuples — a per-parameter
coercion spec converts 2-element lists back before every call, so the target sees
the same value the annotation promises.

**Does it use Gemma?**
Yes — Gemma 4 via the Gemini API (`gemma-4-26b-a4b-it` default,
`gemma-4-31b-it` opt-in) or fully offline via llama.cpp (`--provider local`).

**Can I run it with no network?**
`capture`, `verify`, `bench` and `--provider local`/`file` need no network.

**What does `smelt apply` do?**
Prints the proposed change (new-file diff + build command + try/except shim).
View only — it never writes into your repository.

**Where do the numbers come from?**
Every table in this repo is generated from real run output; each number is
labeled with the model that produced it. Nothing is rounded up; failures stay
in the tables.
