"""Multi-parameter widening tests (G1 step): case generation + capture.

The full end-to-end gate for this widening is the extended meta-eval
(13/13 wrong rewrites rejected — scripts/meta_eval.py) plus a real accept of
`examples/demo/divide.py:divide` with tests/fixtures/candidates/divide_correct.rs.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from smelt_rs.oracle.capture import generate_cases  # noqa: E402


def _params(*annotations):
    return [{"name": f"p{i}", "annotation": a, "default": None}
            for i, a in enumerate(annotations)]


def test_single_param_unchanged_size():
    cases = generate_cases(_params("str"), 200, seed=1234)
    assert len(cases) == 200 + len(__import__("smelt_rs.oracle.capture", fromlist=["EDGE_STRINGS"]).EDGE_STRINGS)
    assert all(len(c["args"]) == 1 for c in cases)


def test_two_params_generation():
    cases = generate_cases(_params("int", "int"), 200, seed=7)
    assert len(cases) >= 40
    assert all(len(c["args"]) == 2 for c in cases)
    assert all(isinstance(a, int) and isinstance(b, int) for a, b in (c["args"] for c in cases))
    # edge product must include the zero/zero pair (ZeroDivisionError cases)
    assert any(c["args"] == [0, 0] for c in cases)


def test_three_params_generation():
    cases = generate_cases(_params("int", "int", "int"), 200, seed=7)
    assert len(cases) >= 40
    assert all(len(c["args"]) == 3 for c in cases)


def test_multi_param_mixed_types():
    cases = generate_cases(_params("str", "int"), 120, seed=3)
    assert len(cases) >= 40
    for c in cases:
        assert isinstance(c["args"][0], str) and isinstance(c["args"][1], int)


def test_unsupported_type_still_refused():
    import pytest
    from smelt_rs.core.failures import RefusedTarget
    with pytest.raises(RefusedTarget):
        generate_cases(_params("Iterable[int]"), 50, seed=1)
