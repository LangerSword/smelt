# smelt — blind generalization re-run (generated — never hand-edited)

Same frozen list (`evals/general_frozen_list.json`, sha256 `1fbdb6bf8cdfa4f4…` — functions never swapped). Pipeline: v0.8 (repair loop, package loading, domain guard).
Provider `nvidia` · model `mistralai/mistral-large-4-1t-a52b` · max-attempts 2 · call cap 50. Protocol delta vs the Oct-2026 run: provider/model (then gemini/gemma-4-26b-a4b-it) and the upgraded pipeline; the list is identical.

Repo commits at run time: humanize `a95004512dde` · validators `22786cc6e728` · shortuuid `75a7803c3633`

| # | repo | function | expected | outcome | reason | speedup (lb) | attempts |
|---|---|---|---|---|---|---|---|
| 1 | humanize | `src/humanize/number.py:apnumber` | easy | refused | refused_unsupported_target: could not load the target module: ModuleNotFoundError: No module named 'humanize._version' — | — | 0 |
| 2 | humanize | `src/humanize/number.py:ordinal` | easy | refused | refused_unsupported_target: could not load the target module: ModuleNotFoundError: No module named 'humanize._version' — | — | 0 |
| 3 | validators | `src/validators/hashes.py:md5` | easy | refused | refused_unsupported_target: could not load the target module: ModuleNotFoundError: No module named 'validators' — packag | — | 0 |
| 4 | humanize | `src/humanize/lists.py:natural_list` | medium | refused | refused_unsupported_target: could not load the target module: ModuleNotFoundError: No module named 'humanize._version' — | — | 0 |
| 5 | validators | `src/validators/email.py:email` | medium | refused | refused_unsupported_target: could not load the target module: ModuleNotFoundError: No module named 'validators' — packag | — | 0 |
| 6 | validators | `src/validators/ip_address.py:ipv4` | medium | refused | refused_unsupported_target: could not load the target module: ModuleNotFoundError: No module named 'validators' — packag | — | 0 |
| 7 | shortuuid | `shortuuid/main.py:encode` | object | refused | refused_impure: impure target: module imports 'secrets' (side effects / nondeterminism) | — | 0 |
| 8 | shortuuid | `shortuuid/main.py:ShortUUID.encode` | object | config_error | function 'ShortUUID.encode' not found in /home/lakshaya/.hermes/cache/scratch/smelt-blind-v08/repos/shortuuid/shortuuid/ | — | 0 |
| 9 | humanize | `src/humanize/time.py:naturaltime` | impure | refused | refused_unsupported_target: could not load the target module: ModuleNotFoundError: No module named 'humanize._version' — | — | 0 |
| 10 | shortuuid | `shortuuid/main.py:uuid` | impure | refused | refused_impure: impure target: module imports 'secrets' (side effects / nondeterminism) | — | 0 |

**Totals:** accepted 0 · rejected 0 · refused 9 · config errors 1 · other errors 0 · provider calls 0 (cap 50).
