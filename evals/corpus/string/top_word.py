"""Most frequent word (letters only, lowercase); ties break alphabetically."""


def top_word(text: str) -> str:
    """Most frequent a-z word in text (lowercased); ties: smallest word wins; '' -> ''."""
    words = []
    cur = []
    for ch in text.lower():
        if "a" <= ch <= "z":
            cur.append(ch)
        elif cur:
            words.append("".join(cur))
            cur = []
    if cur:
        words.append("".join(cur))
    if not words:
        return ""
    counts = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    best = ""
    best_n = -1
    for w in sorted(counts):
        if counts[w] > best_n:
            best, best_n = w, counts[w]
    return best
