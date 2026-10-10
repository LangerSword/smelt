"""Maximum subarray sum (Kadane, empty segments allowed); empty -> 0."""


def max_subarray(vals: list[int]) -> int:
    best = 0
    cur = 0
    for v in vals:
        cur += v
        if cur < 0:
            cur = 0
        if cur > best:
            best = cur
    return best
