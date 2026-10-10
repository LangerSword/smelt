"""Length of the longest run of consecutive ASCII letters."""


def longest_alpha_run(text: str) -> int:
    best = 0
    cur = 0
    for ch in text:
        if ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best
