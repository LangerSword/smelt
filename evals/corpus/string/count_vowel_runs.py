"""Count runs of consecutive vowels (aeiou, case-insensitive)."""


def count_vowel_runs(text: str) -> int:
    vowels = set("aeiou")
    runs = 0
    in_run = False
    for ch in text.lower():
        is_v = ch in vowels
        if is_v and not in_run:
            runs += 1
        in_run = is_v
    return runs
