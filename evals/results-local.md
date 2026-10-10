# smelt eval results (generated — never hand-edited)

- provider `local` · model `gemma-4-e2b-qat` · ran on laptop
- tasks 24 · completed 24 · accepted 18 · rejected 6 · other 0
- provider calls: {'attempts': 44, 'ok': 44, 'by_model': {'gemma-4-e2b-qat': 44}} (cap 200)

| function | cat | status | attempts | oracle | speedup | lb | notes |
|---|---|---|---|---|---|---|---|
| `linear_score` | float | rejected | 3 | 206 | 1.26x | 1.22x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.26x, l |
| `sigmoid_approx` | float | rejected | 3 | 206 | 1.51x | 1.42x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.51x, l |
| `collatz_steps` | int | accepted | 1 | 209 | 22.75x | 22.29x | verified 209/209 cases; speedup 22.75x (conservative lower bound 22.29x) |
| `digital_root` | int | accepted | 2 | 209 | 2.58x | 2.54x | verified 209/209 cases; speedup 2.58x (conservative lower bound 2.54x) |
| `popcount` | int | accepted | 1 | 209 | 4.00x | 3.95x | verified 209/209 cases; speedup 4.00x (conservative lower bound 3.95x) |
| `reverse_digits` | int | accepted | 1 | 209 | 2.93x | 2.86x | verified 209/209 cases; speedup 2.93x (conservative lower bound 2.86x) |
| `sum_digits_sq` | int | accepted | 1 | 209 | 2.96x | 2.89x | verified 209/209 cases; speedup 2.96x (conservative lower bound 2.89x) |
| `triangular` | int | accepted | 3 | 209 | 24.33x | 24.15x | verified 209/209 cases; speedup 24.33x (conservative lower bound 24.15x) |
| `bucket_hash` | list | accepted | 1 | 204 | 1.72x | 1.71x | verified 204/204 cases; speedup 1.72x (conservative lower bound 1.71x) |
| `count_peaks` | list | accepted | 1 | 204 | 2.00x | 1.94x | verified 204/204 cases; speedup 2.00x (conservative lower bound 1.94x) |
| `longest_run` | list | accepted | 2 | 204 | 1.64x | 1.53x | verified 204/204 cases; speedup 1.64x (conservative lower bound 1.53x) |
| `max_subarray` | list | accepted | 1 | 204 | 1.77x | 1.70x | verified 204/204 cases; speedup 1.77x (conservative lower bound 1.70x) |
| `median_doubled` | list | rejected | 3 | 204 | 1.23x | 1.22x | no candidate accepted within 3 attempt(s); last: safety_violation: safety scan failed: mis |
| `prefix_max_sum` | list | rejected | 3 | 204 | 1.48x | 1.41x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.48x, l |
| `sum_squares` | list | accepted | 2 | 204 | 1.74x | 1.63x | verified 204/204 cases; speedup 1.74x (conservative lower bound 1.63x) |
| `caesar_shift` | string | accepted | 1 | 225 | 8.13x | 8.06x | verified 225/225 cases; speedup 8.13x (conservative lower bound 8.06x) |
| `count_vowel_runs` | string | accepted | 1 | 225 | 5.56x | 5.49x | verified 225/225 cases; speedup 5.56x (conservative lower bound 5.49x) |
| `count_words` | string | accepted | 1 | 225 | 8.08x | 8.04x | verified 225/225 cases; speedup 8.08x (conservative lower bound 8.04x) |
| `is_palindrome_norm` | string | accepted | 3 | 225 | 2.86x | 2.85x | verified 225/225 cases; speedup 2.86x (conservative lower bound 2.85x) |
| `longest_alpha_run` | string | accepted | 1 | 225 | 9.72x | 9.65x | verified 225/225 cases; speedup 9.72x (conservative lower bound 9.65x) |
| `normalize_spaces` | string | rejected | 3 | 225 | 1.19x | 1.17x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.19x, l |
| `reverse_words` | string | accepted | 2 | 225 | 1.73x | 1.68x | verified 225/225 cases; speedup 1.73x (conservative lower bound 1.68x) |
| `snake_to_camel` | string | accepted | 1 | 225 | 2.07x | 1.97x | verified 225/225 cases; speedup 2.07x (conservative lower bound 1.97x) |
| `top_word` | string | rejected | 3 | 225 | — | — | no candidate accepted within 3 attempt(s); last: build_error[api_drift]: cargo build faile |
