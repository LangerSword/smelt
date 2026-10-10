"""Alphanumeric-only, case-insensitive palindrome check."""


def is_palindrome_norm(text: str) -> bool:
    chars = [ch.lower() for ch in text if ch.isalnum()]
    return chars == chars[::-1]
