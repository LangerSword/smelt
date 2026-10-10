"""Sum of squares of values; empty -> 0."""


def sum_squares(vals: list[int]) -> int:
    total = 0
    for v in vals:
        total += v * v
    return total
