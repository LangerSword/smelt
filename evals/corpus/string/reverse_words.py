"""Reverse word order (whitespace-separated), single-space join."""


def reverse_words(text: str) -> str:
    return " ".join(reversed(text.split()))
