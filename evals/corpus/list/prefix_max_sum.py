"""Sum of running maxima; empty -> 0."""


def prefix_max_sum(vals: list[int]) -> int:
    total = 0
    best = None
    for v in vals:
        if best is None or v > best:
            best = v
        total += best
    return total
