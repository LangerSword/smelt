"""Longest run of equal consecutive values; empty -> 0."""


def longest_run(vals: list[int]) -> int:
    best = 0
    cur = 0
    prev = None
    for v in vals:
        if v == prev:
            cur += 1
        else:
            cur = 1
            prev = v
        if cur > best:
            best = cur
    return best
