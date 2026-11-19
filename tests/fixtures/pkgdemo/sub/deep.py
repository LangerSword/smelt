from ..helpers import double


def sum_doubled_deep(xs: list[int]) -> int:
    return sum(double(x) for x in xs) + 1
