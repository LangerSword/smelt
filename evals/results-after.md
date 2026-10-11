# smelt eval results (generated — never hand-edited)

- provider `gemini` · model `gemma-4-26b-a4b-it` · ran on laptop
- tasks 24 · completed 24 · accepted 23 · rejected 1 · other 0
- provider calls: {'attempts': 27, 'ok': 27, 'by_model': {'gemma-4-26b-a4b-it': 27}} (cap 120)

| function | cat | status | attempts | oracle | speedup | lb | notes |
|---|---|---|---|---|---|---|---|
| `linear_score` | float | accepted | 1 | 206 | 1.62x | 1.57x | verified 206/206 cases; speedup 1.62x (conservative lower bound 1.57x) |
| `sigmoid_approx` | float | accepted | 1 | 206 | 1.55x | 1.51x | verified 206/206 cases; speedup 1.55x (conservative lower bound 1.51x) |
| `collatz_steps` | int | accepted | 1 | 209 | 23.54x | 21.63x | verified 209/209 cases; speedup 23.54x (conservative lower bound 21.63x) |
| `digital_root` | int | accepted | 1 | 209 | 2.72x | 2.72x | verified 209/209 cases; speedup 2.72x (conservative lower bound 2.72x) |
| `popcount` | int | accepted | 1 | 209 | 3.45x | 3.33x | verified 209/209 cases; speedup 3.45x (conservative lower bound 3.33x) |
| `reverse_digits` | int | accepted | 1 | 209 | 2.45x | 2.39x | verified 209/209 cases; speedup 2.45x (conservative lower bound 2.39x) |
| `sum_digits_sq` | int | accepted | 1 | 209 | 3.22x | 2.83x | verified 209/209 cases; speedup 3.22x (conservative lower bound 2.83x) |
| `triangular` | int | accepted | 1 | 209 | 46.72x | 46.69x | verified 209/209 cases; speedup 46.72x (conservative lower bound 46.69x) |
| `bucket_hash` | list | accepted | 1 | 204 | 2.04x | 1.95x | verified 204/204 cases; speedup 2.04x (conservative lower bound 1.95x) |
| `count_peaks` | list | accepted | 1 | 204 | 2.11x | 2.05x | verified 204/204 cases; speedup 2.11x (conservative lower bound 2.05x) |
| `longest_run` | list | accepted | 1 | 204 | 1.68x | 1.62x | verified 204/204 cases; speedup 1.68x (conservative lower bound 1.62x) |
| `max_subarray` | list | accepted | 1 | 204 | 1.61x | 1.58x | verified 204/204 cases; speedup 1.61x (conservative lower bound 1.58x) |
| `median_doubled` | list | accepted | 2 | 204 | 1.59x | 1.58x | verified 204/204 cases; speedup 1.59x (conservative lower bound 1.58x) |
| `prefix_max_sum` | list | accepted | 1 | 204 | 1.61x | 1.56x | verified 204/204 cases; speedup 1.61x (conservative lower bound 1.56x) |
| `sum_squares` | list | accepted | 1 | 204 | 1.73x | 1.68x | verified 204/204 cases; speedup 1.73x (conservative lower bound 1.68x) |
| `caesar_shift` | string | accepted | 1 | 225 | 15.01x | 13.76x | verified 225/225 cases; speedup 15.01x (conservative lower bound 13.76x) |
| `count_vowel_runs` | string | accepted | 1 | 225 | 5.34x | 5.31x | verified 225/225 cases; speedup 5.34x (conservative lower bound 5.31x) |
| `count_words` | string | accepted | 1 | 225 | 7.94x | 7.34x | verified 225/225 cases; speedup 7.94x (conservative lower bound 7.34x) |
| `is_palindrome_norm` | string | accepted | 1 | 225 | 2.99x | 2.94x | verified 225/225 cases; speedup 2.99x (conservative lower bound 2.94x) |
| `longest_alpha_run` | string | accepted | 1 | 225 | 10.74x | 10.00x | verified 225/225 cases; speedup 10.74x (conservative lower bound 10.00x) |
| `normalize_spaces` | string | rejected | 3 | 225 | 1.18x | 1.14x | no candidate accepted within 3 attempt(s); last: reject_no_meaningful_gain: ratio 1.18x, l |
| `reverse_words` | string | accepted | 1 | 225 | 1.94x | 1.84x | verified 225/225 cases; speedup 1.94x (conservative lower bound 1.84x) |
| `snake_to_camel` | string | accepted | 1 | 225 | 2.85x | 2.72x | verified 225/225 cases; speedup 2.85x (conservative lower bound 2.72x) |
| `top_word` | string | accepted | 1 | 225 | 5.19x | 5.02x | verified 225/225 cases; speedup 5.19x (conservative lower bound 5.02x) |
