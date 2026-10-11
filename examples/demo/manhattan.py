def manhattan(p: tuple[int, int]) -> int:
    """Manhattan distance from the origin for one integer point."""
    x, y = p
    return abs(x) + abs(y)
