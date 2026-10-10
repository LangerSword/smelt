"""Iterated digit sum; n < 0 -> -1."""


def digital_root(n: int) -> int:
    if n < 0:
        return -1
    while n >= 10:
        total = 0
        while n > 0:
            total += n % 10
            n //= 10
        n = total
    return n
