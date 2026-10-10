"""Count words (maximal runs of a-z after lowercasing)."""


def count_words(text: str) -> int:
    """Maximal runs of letters a-z, case-insensitive. '' -> 0."""
    count = 0
    in_word = False
    for ch in text.lower():
        is_letter = "a" <= ch <= "z"
        if is_letter and not in_word:
            count += 1
        in_word = is_letter
    return count
