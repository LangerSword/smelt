"""Shift ASCII letters by one (z->a, Z->A); other characters unchanged."""


def caesar_shift(text: str) -> str:
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + 1) % 26 + 97))
        elif "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + 1) % 26 + 65))
        else:
            out.append(ch)
    return "".join(out)
