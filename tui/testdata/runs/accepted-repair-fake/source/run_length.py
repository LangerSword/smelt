"""Demo target for smelt: run-length encoder.

Pure, deterministic, no imports, annotated. Written during the event as the
end-to-end demo function (v0.1-core gate).
"""


def rle_encode(text: str) -> str:
    """Encode maximal runs of identical characters as <char><count>.

    Counts are always included (even for single characters).
    rle_encode("aabb") == "a2b2"; rle_encode("") == "".
    """
    if not text:
        return ""
    out = []
    prev = text[0]
    count = 0
    for ch in text:
        if ch == prev:
            count += 1
        else:
            out.append(prev + str(count))
            prev = ch
            count = 1
    out.append(prev + str(count))
    return "".join(out)
