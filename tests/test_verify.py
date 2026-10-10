"""Unit tests for the verifier's comparison semantics (fast, no cargo involved)."""

from smelt_rs.oracle.verify import compare, values_equal


def enc(t: str, v: object = "__none__"):
    return {"t": t} if v == "__none__" else {"t": t, "v": v}


def test_values_equal_scalars():
    assert values_equal(enc("int", 3), enc("int", 3))
    assert not values_equal(enc("int", 3), enc("int", 4))
    assert values_equal(enc("str", "a"), enc("str", "a"))
    assert not values_equal(enc("str", "a"), enc("str", "b"))
    assert values_equal(enc("none"), enc("none"))


def test_values_equal_floats_tolerance():
    assert values_equal(enc("float", 1.0), enc("float", 1.0 + 1e-12))
    assert not values_equal(enc("float", 1.0), enc("float", 1.1))
    assert values_equal(enc("float", "nan"), enc("float", "nan"))
    assert not values_equal(enc("float", "nan"), enc("float", 0.0))
    assert not values_equal(enc("float", "inf"), enc("float", "-inf"))


def test_values_equal_lists():
    a = enc("list", [enc("int", 1), enc("int", 2)])
    b = enc("list", [enc("int", 1), enc("int", 2)])
    c = enc("list", [enc("int", 1)])
    assert values_equal(a, b)
    assert not values_equal(a, c)
    assert not values_equal(a, enc("list", [enc("int", 2), enc("int", 1)]))


def test_compare_flags_output_mismatch():
    entries = [{"case_id": "r0000", "args": ["a"], "kwargs": {}, "expected_ok": True,
                "expected": enc("str", "x"), "expected_err": None}]
    rust = [{"id": "r0000", "ok": True, "out": enc("str", "y")}]
    n, sample = compare(entries, rust)
    assert n == 1
    assert sample[0]["why"] == "output differs"


def test_compare_flags_outcome_kind():
    entries = [{"case_id": "r0000", "args": [1], "kwargs": {}, "expected_ok": True,
                "expected": enc("int", 1), "expected_err": None}]
    rust = [{"id": "r0000", "ok": False, "err": "OverflowError"}]
    n, _ = compare(entries, rust)
    assert n == 1


def test_compare_missing_result_is_mismatch():
    entries = [{"case_id": "r0000", "args": [1], "kwargs": {}, "expected_ok": True,
                "expected": enc("int", 1), "expected_err": None}]
    n, sample = compare(entries, [])
    assert n == 1
    assert sample[0]["why"] == "missing result"
