# smelt — blind generalization test (generated — never hand-edited)

Run of **3 real open-source repos / 10 functions**, list frozen BEFORE any run
(`frozen_list.json`, sha256 in the freeze proof), **no oracle or code changes**
(smelt HEAD `fa00e109ca32c0adda1116614570ad0893b89c50`).
Provider `gemini` · model `gemma-4-26b-a4b-it` · max-attempts 2 · call cap 50.

Repos: [humanize](https://github.com/python-humanize/humanize) (MIT) · [validators](https://github.com/python-validators/validators) (MIT) · [shortuuid](https://github.com/skorokithakis/shortuuid) (BSD-3).

| # | repo | function | expected | outcome | reason (from state.json) | speedup (lb) | attempts | model | time (s) | calls |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | humanize | `src/humanize/number.py:apnumber` | easy | error | capture_failed: target function has no parameters (nothing to test) | — | 0 | gemma-4-26b-a4b-it | 0.2 | 0 |
| 2 | humanize | `src/humanize/number.py:ordinal` | easy | error | capture_failed: target function has no parameters (nothing to test) | — | 0 | gemma-4-26b-a4b-it | 0.2 | 0 |
| 3 | validators | `src/validators/hashes.py:md5` | easy | error | capture_failed: target function has no parameters (nothing to test) | — | 0 | gemma-4-26b-a4b-it | 0.2 | 0 |
| 4 | humanize | `src/humanize/lists.py:natural_list` | medium | error | capture_failed: unsupported parameter type for generation: 'Iterable[Any]' | — | 0 | gemma-4-26b-a4b-it | 0.1 | 0 |
| 5 | validators | `src/validators/email.py:email` | medium | error | capture_failed: target function has no parameters (nothing to test) | — | 0 | gemma-4-26b-a4b-it | 0.1 | 0 |
| 6 | validators | `src/validators/ip_address.py:ipv4` | medium | error | capture_failed: target function has no parameters (nothing to test) | — | 0 | gemma-4-26b-a4b-it | 0.1 | 0 |
| 7 | shortuuid | `shortuuid/main.py:encode` | object | refused | refused_impure: impure target: module imports 'secrets' (side effects / nondeterminism) | — | 0 | gemma-4-26b-a4b-it | 0.1 | 0 |
| 8 | shortuuid | `shortuuid/main.py:ShortUUID.encode` | object | refused | refused_impure: impure target: function 'ShortUUID.encode' not found in /home/lakshaya/.hermes/cache/scratch/hacktober2026/general/repos/sho | — | 0 | gemma-4-26b-a4b-it | 0.1 | 0 |
| 9 | humanize | `src/humanize/time.py:naturaltime` | impure | error | capture_failed: target function has no parameters (nothing to test) | — | 0 | gemma-4-26b-a4b-it | 0.1 | 0 |
| 10 | shortuuid | `shortuuid/main.py:uuid` | impure | refused | refused_impure: impure target: module imports 'secrets' (side effects / nondeterminism) | — | 0 | gemma-4-26b-a4b-it | 0.1 | 0 |

**Totals:** 10/10 run · accepted 0 · rejected 0 · refused 3 · other 7 · **total provider calls 0** (cap 50).

## Why each function was picked (frozen before the run)

- 1. `humanize` `src/humanize/number.py:apnumber` — expected **easy** — number→word formatter; one value param (custom NumberOrString alias)
- 2. `humanize` `src/humanize/number.py:ordinal` — expected **easy** — ordinal number formatter; one required param + optional gender kwarg
- 3. `validators` `src/validators/hashes.py:md5` — expected **easy** — checksum validator; plain str, positional-only; decorated with @validator
- 4. `humanize` `src/humanize/lists.py:natural_list` — expected **medium** — loops an iterable of items; nested list input
- 5. `validators` `src/validators/email.py:email` — expected **medium** — regex-heavy string validation; one required str + keyword-only extras
- 6. `validators` `src/validators/ip_address.py:ipv4` — expected **medium** — multi-branch string parsing; one required str + keyword-only extras
- 7. `shortuuid` `shortuuid/main.py:encode` — expected **object** — bound method alias; takes a UUID object (unsupported type expected)
- 8. `shortuuid` `shortuuid/main.py:ShortUUID.encode` — expected **object** — dotted class method; UUID object; probes qualname resolution
- 9. `humanize` `src/humanize/time.py:naturaltime` — expected **impure** — time-dependent (defaults to now); datetime/timedelta/float value
- 10. `shortuuid` `shortuuid/main.py:uuid` — expected **impure** — randomness (uuid/random imports); bound global method, zero required args

## Findings (listed, NOT fixed during the test)

**BUG-1 (high, root-caused): package files fail to load; the real error is swallowed and reported as "target function has no parameters".** Six of ten functions (`apnumber`, `ordinal`, `md5`, `email`, `ipv4`, `naturaltime`) live in files with relative imports (`from .i18n import …`, `from .utils import validator`). The worker loads target files as standalone modules (`_load_fn`: `spec_from_file_location` + `exec_module`), which fails with `ImportError: attempted relative import with no known parent package` (reproduced directly). The worker returns `{ok: false, error: "ImportError: …"}`; `run_worker` does not surface it; `capture_oracle` then reports "no parameters" — a misleading message that hides the cause. Evidence: the one file without relative imports (`lists.py`, `natural_list`) introspected correctly and produced a precise message. Impact: today the tool works on single-file targets; real-repo (package) targets fail at load with a wrong message. Exit 5, zero API calls.

**BUG-2 (medium): dotted qualnames unsupported and mislabeled.** `main.py:ShortUUID.encode` → "function 'ShortUUID.encode' not found in …/main.py", classified `refused_impure` (exit 3). It is a resolution failure, not an impurity refusal — the kind label and exit code are wrong even though the message text is readable.

**BUG-3 (low): unsupported parameter types classify as error, not refusal.** `natural_list` (annotation `Iterable[Any]`) produced a precise message ("unsupported parameter type for generation: 'Iterable[Any]'") but lands as `capture_failed` / exit 5 instead of a typed refusal outcome.

**Correct behaviour observed:** shortuuid targets (`encode`, `uuid`) were refused cleanly at the purity probe — "module imports 'secrets' (side effects / nondeterminism)" — exit 3, zero API calls. Module-level purity scanning is conservative and its message is clear.

**No crashes:** all ten outcomes carried an exit code and a typed reason (two reasons were misleading per BUG-1/BUG-2). **Total provider calls: 0** — the tool never reached generation for any function. Nothing was accepted, so "zero wrong accepts" is trivially true here but untested on this corpus (false-accept prevention is covered by the meta-eval 10/10 and the L1/L2 runs).

**Interpretation (honest):** the blind test did not measure the tier system — it surfaced a loading prerequisite. The package-aware load + surfacing the real ImportError is the minimum fix before any real-repo claim, and before G1/G2 oracle widening is meaningful.

