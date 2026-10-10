"""Verifier: compare Rust outcomes against the frozen oracle.

Semantics (documented limits):
- outcome parity: if the Python original raised, the Rust side must also raise
  (exception TYPE equality is not required — pyo3 error mapping differs).
- if both returned: encoded values must be equal (ints/str exact; floats with a
  relative tolerance; NaN==NaN; inf==inf).
- lists compared element-wise; dicts by key.
Reviewed closely by the developer.
"""


def values_equal(a: dict | None, b: dict | None, rtol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    if a.get("t") != b.get("t"):
        if {a.get("t"), b.get("t")} == {"int", "float"}:
            return _num_close(a.get("v"), b.get("v"), rtol)
        return False
    t = a.get("t")
    if t == "float":
        av, bv = a.get("v"), b.get("v")
        if av in ("nan", "inf", "-inf") or bv in ("nan", "inf", "-inf"):
            return av == bv
        return _num_close(av, bv, rtol)
    if t == "list":
        if len(a.get("v", [])) != len(b.get("v", [])):
            return False
        return all(values_equal(x, y, rtol) for x, y in zip(a["v"], b["v"]))
    if t == "dict":
        ka, kb = set(a.get("v", {})), set(b.get("v", {}))
        if ka != kb:
            return False
        return all(values_equal(a["v"][k], b["v"][k], rtol) for k in ka)
    return a.get("v") == b.get("v")


def _num_close(x, y, rtol: float) -> bool:
    try:
        return abs(x - y) <= rtol * max(1.0, abs(x), abs(y))
    except TypeError:
        return False


def compare(entries: list[dict], rust_results: list[dict], max_report: int = 8):
    """Returns (n_mismatch, sample). Compares every case; sample is capped for honesty+brevity."""
    by_id = {r["id"]: r for r in rust_results}
    n_mismatch = 0
    sample = []
    for e in entries:
        r = by_id.get(e["case_id"])
        why = None
        if r is None:
            why = "missing result"
        elif e["expected_ok"] != bool(r.get("ok")):
            why = "outcome kind differs (returned vs raised)"
        elif e["expected_ok"] and not values_equal(e["expected"], r.get("out")):
            why = "output differs"
        if why:
            n_mismatch += 1
            if len(sample) < max_report:
                got = r if r is not None else {}
                sample.append({"case_id": e["case_id"], "why": why, "args": e["args"],
                               "expected": e["expected"], "got": got.get("out"),
                               "expected_err": e.get("expected_err"), "got_err": got.get("err")})
    return n_mismatch, sample
