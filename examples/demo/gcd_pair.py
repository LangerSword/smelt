def gcd_pair(p: tuple[int, int]) -> int:
    """Euclid's GCD of an integer pair (absolute values; loop-heavy on purpose)."""
    a, b = abs(p[0]), abs(p[1])
    while b:
        a, b = b, a % b
    return a
