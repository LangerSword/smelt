# smelt eval corpus — frozen function list

24 single-parameter pure functions, written fresh during the event and committed
BEFORE the first eval run (anti-cherry-pick rule). One parameter per function
(str | int | float | list[int]); integers live in the 64-bit domain.

| # | function | category | sample result |
|---|----------|----------|---------------|
| 1 | `linear_score` | float | `0.9249999999999998` |
| 2 | `sigmoid_approx` | float | `0.8175744761936437` |
| 3 | `collatz_steps` | int | `46` |
| 4 | `digital_root` | int | `6` |
| 5 | `popcount` | int | `6` |
| 6 | `reverse_digits` | int | `321` |
| 7 | `sum_digits_sq` | int | `14` |
| 8 | `triangular` | int | `7626` |
| 9 | `bucket_hash` | list | `1026` |
| 10 | `count_peaks` | list | `0` |
| 11 | `longest_run` | list | `1` |
| 12 | `max_subarray` | list | `3` |
| 13 | `median_doubled` | list | `2` |
| 14 | `prefix_max_sum` | list | `5` |
| 15 | `sum_squares` | list | `14` |
| 16 | `caesar_shift` | string | `'bbccd1!'` |
| 17 | `count_vowel_runs` | string | `1` |
| 18 | `count_words` | string | `1` |
| 19 | `is_palindrome_norm` | string | `False` |
| 20 | `longest_alpha_run` | string | `5` |
| 21 | `normalize_spaces` | string | `'aabbc1!'` |
| 22 | `reverse_words` | string | `'aabbc1!'` |
| 23 | `snake_to_camel` | string | `'aabbc1!'` |
| 24 | `top_word` | string | `'aabbc'` |
