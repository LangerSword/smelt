"""Sum of squares of decimal digits; n < 0 -> -1."""


def sum_digits_sq(n: int) -> int:
    if n < 0:
        return -1
    total = 0
    while n > 0:
        d = n % 10
        total += d * d
        n //= 10
    return total
