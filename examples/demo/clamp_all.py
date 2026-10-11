def clamp_all(values: list[int], lo: int, hi: int) -> list[int]:
    """Clamp each value into [lo, hi] (three parameters: list[int], int, int)."""
    return [min(max(v, lo), hi) for v in values]
