"""Fixed affine transform, float-op-identical on both sides."""


def linear_score(x: float) -> float:
    return ((x * 1.7 + 3.3) * 0.5) - 2.0
