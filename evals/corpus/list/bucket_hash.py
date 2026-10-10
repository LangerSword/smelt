"""Polynomial bucket hash over abs(v), modulo 1_000_000_007; empty -> 0."""


def bucket_hash(vals: list[int]) -> int:
    h = 0
    for v in vals:
        h = (h * 31 + abs(v)) % 1_000_000_007
    return h
