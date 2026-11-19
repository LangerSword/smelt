# smelt eval results (generated — never hand-edited)

- provider `nvidia` · model `mistralai/mistral-large-4-1t-a52b` · ran on laptop
- tasks 24 · completed 24 · accepted 10 · rejected 0 · timeouts 12 · other 2
- provider calls: {'attempts': 44, 'ok': 21, 'by_model': {'mistralai/mistral-large-4-1t-a52b': 21}} (cap 120)
- repair loop: on · per-task wall-clock cap: 600s (capped tasks record as timeout — NIM stalls on long-reasoning prompts)

| function | cat | status | attempts | oracle | speedup | lb | notes |
|---|---|---|---|---|---|---|---|
| `linear_score` | float | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `sigmoid_approx` | float | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `collatz_steps` | int | accepted | 1 | 209 | 7.80x | 7.77x | verified 209/209 cases; speedup 7.80x (conservative lower bound 7.77x) |
| `digital_root` | int | accepted | 1 | 209 | 1.79x | 1.76x | verified 209/209 cases; speedup 1.79x (conservative lower bound 1.76x) |
| `popcount` | int | accepted | 1 | 209 | 2.25x | 2.24x | verified 209/209 cases; speedup 2.25x (conservative lower bound 2.24x) |
| `reverse_digits` | int | accepted | 1 | 209 | 1.65x | 1.64x | verified 209/209 cases; speedup 1.65x (conservative lower bound 1.64x) |
| `sum_digits_sq` | int | accepted | 1 | 209 | 1.55x | 1.53x | verified 209/209 cases; speedup 1.55x (conservative lower bound 1.53x) |
| `triangular` | int | accepted | 1 | 209 | 19598.27x | 19567.82x | verified 209/209 cases; speedup 19598.27x (conservative lower bound 19567.82x) |
| `bucket_hash` | list | accepted | 1 | 204 | 1.60x | 1.60x | verified 204/204 cases; speedup 1.60x (conservative lower bound 1.60x) |
| `count_peaks` | list | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `longest_run` | list | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `max_subarray` | list | error | 2 | 204 | 1.33x | 1.33x | provider_error: empty completion from provider (finish_reason=length; reasoning may have e |
| `median_doubled` | list | error | 1 | 204 | — | — | provider_error: empty completion from provider (finish_reason=length; reasoning may have e |
| `prefix_max_sum` | list | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `sum_squares` | list | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `caesar_shift` | string | accepted | 1 | 225 | 5.93x | 5.91x | verified 225/225 cases; speedup 5.93x (conservative lower bound 5.91x) |
| `count_vowel_runs` | string | accepted | 1 | 225 | 2.33x | 2.32x | verified 225/225 cases; speedup 2.33x (conservative lower bound 2.32x) |
| `count_words` | string | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `is_palindrome_norm` | string | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `longest_alpha_run` | string | accepted | 1 | 225 | 3.44x | 3.42x | verified 225/225 cases; speedup 3.44x (conservative lower bound 3.42x) |
| `normalize_spaces` | string | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `reverse_words` | string | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `snake_to_camel` | string | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
| `top_word` | string | timeout | 0 | None | — | — | task wall-clock cap (600s) — provider call did not return |
