"""Collatz steps to reach 1; n < 1 or n > 10_000_000 -> -1."""


def collatz_steps(n: int) -> int:
    if n < 1 or n > 10_000_000:
        return -1
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n //= 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps
