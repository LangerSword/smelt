from .helpers import double


def sum_doubled(xs: list[int]) -> int:
    return sum(double(x) for x in xs)
