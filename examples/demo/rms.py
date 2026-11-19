import math


def rms(xs: list[float]) -> float:
    if not xs:
        raise ValueError("empty sample")
    return math.sqrt(sum(x * x for x in xs) / len(xs))
