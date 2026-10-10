"""Reverse decimal digits as an integer; n < 0 -> -1."""


def reverse_digits(n: int) -> int:
    if n < 0:
        return -1
    out = 0
    while n > 0:
        out = out * 10 + n % 10
        n //= 10
    return out
