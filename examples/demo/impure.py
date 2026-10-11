import random


def noisy_max(vals: list[int]) -> int:
    """Impure on purpose: the purity probe refuses this (imports random)."""
    if random.random() < 0.5:
        return max(vals)
    return min(vals)
