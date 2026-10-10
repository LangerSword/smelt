"""1 / (1 + exp(-x)) using the standard library exp."""

import math


def sigmoid_approx(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))
