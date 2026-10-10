"""foo_bar_baz -> fooBarBaz (empty segments ignored)."""


def snake_to_camel(text: str) -> str:
    parts = [p for p in text.split("_") if p != ""]
    if not parts:
        return ""
    out = [parts[0]]
    for p in parts[1:]:
        out.append(p[0].upper() + p[1:])
    return "".join(out)
