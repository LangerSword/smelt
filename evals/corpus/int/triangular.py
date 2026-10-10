"""n-th triangular number via loop; n < 0 or n > 1_000_000 -> -1."""


def triangular(n: int) -> int:
    if n < 0 or n > 1_000_000:
        return -1
    total = 0
    for i in range(1, n + 1):
        total += i
    return total
