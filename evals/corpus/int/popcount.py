"""Number of 1 bits; n < 0 -> -1."""


def popcount(n: int) -> int:
    if n < 0:
        return -1
    count = 0
    while n:
        count += n & 1
        n >>= 1
    return count
