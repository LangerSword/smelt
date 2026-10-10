"""Collapse whitespace runs to single spaces and strip the ends."""


def normalize_spaces(text: str) -> str:
    return " ".join(text.split())
