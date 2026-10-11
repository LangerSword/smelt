import random

def jittery_max(vals: list[int]) -> int:
    if random.random() < 0.5:
        return max(vals)
    return min(vals)
