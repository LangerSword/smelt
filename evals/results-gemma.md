# smelt eval results (generated — never hand-edited)

- provider `gemini` · model `gemma-4-26b-a4b-it` · ran on laptop
- tasks 24 · completed 24 · accepted 20 · rejected 4 · other 0
- provider calls: {'attempts': 36, 'ok': 36, 'by_model': {'gemma-4-26b-a4b-it': 36}} (cap 120)

| function | cat | status | attempts | oracle | speedup | lb | notes |
|---|---|---|---|---|---|---|---|
| `linear_score` | float | rejected | 3 | 206 | 1.41x | 1.37x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.41x, l |
| `sigmoid_approx` | float | accepted | 2 | 206 | 1.65x | 1.60x | verified 206/206 cases; speedup 1.65x (conservative lower bound 1.60x) |
| `collatz_steps` | int | accepted | 1 | 209 | 22.68x | 21.79x | verified 209/209 cases; speedup 22.68x (conservative lower bound 21.79x) |
| `digital_root` | int | accepted | 1 | 209 | 3.32x | 3.24x | verified 209/209 cases; speedup 3.32x (conservative lower bound 3.24x) |
| `popcount` | int | accepted | 1 | 209 | 4.99x | 4.72x | verified 209/209 cases; speedup 4.99x (conservative lower bound 4.72x) |
| `reverse_digits` | int | accepted | 1 | 209 | 2.19x | 2.16x | verified 209/209 cases; speedup 2.19x (conservative lower bound 2.16x) |
| `sum_digits_sq` | int | accepted | 1 | 209 | 3.01x | 2.83x | verified 209/209 cases; speedup 3.01x (conservative lower bound 2.83x) |
| `triangular` | int | accepted | 1 | 209 | 47.14x | 46.97x | verified 209/209 cases; speedup 47.14x (conservative lower bound 46.97x) |
| `bucket_hash` | list | accepted | 2 | 204 | 2.23x | 2.17x | verified 204/204 cases; speedup 2.23x (conservative lower bound 2.17x) |
| `count_peaks` | list | accepted | 1 | 204 | 2.13x | 2.02x | verified 204/204 cases; speedup 2.13x (conservative lower bound 2.02x) |
| `longest_run` | list | accepted | 2 | 204 | 1.64x | 1.54x | verified 204/204 cases; speedup 1.64x (conservative lower bound 1.54x) |
| `max_subarray` | list | accepted | 1 | 204 | 1.72x | 1.56x | verified 204/204 cases; speedup 1.72x (conservative lower bound 1.56x) |
| `median_doubled` | list | rejected | 3 | 204 | 1.38x | 1.35x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.38x, l |
| `prefix_max_sum` | list | rejected | 3 | 204 | 1.46x | 1.41x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.46x, l |
| `sum_squares` | list | accepted | 1 | 204 | 1.74x | 1.66x | verified 204/204 cases; speedup 1.74x (conservative lower bound 1.66x) |
| `caesar_shift` | string | accepted | 1 | 225 | 11.51x | 11.48x | verified 225/225 cases; speedup 11.51x (conservative lower bound 11.48x) |
| `count_vowel_runs` | string | accepted | 1 | 225 | 5.96x | 5.28x | verified 225/225 cases; speedup 5.96x (conservative lower bound 5.28x) |
| `count_words` | string | accepted | 1 | 225 | 7.36x | 6.74x | verified 225/225 cases; speedup 7.36x (conservative lower bound 6.74x) |
| `is_palindrome_norm` | string | accepted | 1 | 225 | 2.40x | 2.39x | verified 225/225 cases; speedup 2.40x (conservative lower bound 2.39x) |
| `longest_alpha_run` | string | accepted | 1 | 225 | 6.77x | 6.30x | verified 225/225 cases; speedup 6.77x (conservative lower bound 6.30x) |
| `normalize_spaces` | string | rejected | 3 | 225 | 1.22x | 1.20x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.22x, l |
| `reverse_words` | string | accepted | 1 | 225 | 1.61x | 1.58x | verified 225/225 cases; speedup 1.61x (conservative lower bound 1.58x) |
| `snake_to_camel` | string | accepted | 1 | 225 | 2.66x | 2.49x | verified 225/225 cases; speedup 2.66x (conservative lower bound 2.49x) |
| `top_word` | string | accepted | 2 | 225 | 4.96x | 4.74x | verified 225/225 cases; speedup 4.96x (conservative lower bound 4.74x) |
