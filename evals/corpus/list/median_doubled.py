"""Sum of the two middle values of the sorted list; empty -> -1."""


def median_doubled(vals: list[int]) -> int:
    if not vals:
        return -1
    s = sorted(vals)
    n = len(s)
    return s[n // 2] + s[(n - 1) // 2]
