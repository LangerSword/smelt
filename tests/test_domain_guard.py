"""i64 domain guard (v0.8): outputs beyond i64 are typed refusals AT CAPTURE.

Previously such targets burned provider calls and surfaced as verify_mismatch —
blaming the model for a domain limit. Now the refusal is immediate, typed
(exit 3), and carries a refactor hint. In-domain targets are unaffected.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from smelt_rs.core import orchestrator  # noqa: E402
from smelt_rs.oracle.capture import first_out_of_i64  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures" / "candidates"


def test_big_output_refused_at_capture(tmp_path):
    code, info = orchestrator.run(
        target=str(REPO / "examples/demo/scale_up.py:scale_up"),
        provider_name="file", candidate=str(FIXTURES / "sum_doubled_correct.rs"),
        runs_dir=str(tmp_path / "runs"), max_attempts=1, target_cases=60, quiet=True)
    assert code == 3, info
    assert info["status"] == "refused", info
    reason = info.get("stop_reason") or ""
    assert "i64 domain" in reason, reason
    assert "refactor hint" in reason, reason


def test_capture_only_also_refuses(tmp_path):
    code, info = orchestrator.capture_only(
        target=str(REPO / "examples/demo/scale_up.py:scale_up"),
        runs_dir=str(tmp_path / "runs"), target_cases=60, quiet=True)
    assert code == 3, info
    assert "i64 domain" in (info.get("stop_reason") or info.get("reason") or ""), info


def test_in_domain_target_unaffected(tmp_path):
    code, info = orchestrator.capture_only(
        target=str(REPO / "evals/corpus/int/popcount.py:popcount"),
        runs_dir=str(tmp_path / "runs"), target_cases=200, quiet=True)
    assert code == 0, info
    assert info["oracle"]["n_cases"] >= 200


def test_first_out_of_i64_unit():
    assert first_out_of_i64(None) is None
    assert first_out_of_i64({"t": "int", "v": 2 ** 63 - 1}) is None
    assert first_out_of_i64({"t": "int", "v": -(2 ** 63)}) is None
    assert first_out_of_i64({"t": "int", "v": 2 ** 63}) == 2 ** 63
    assert first_out_of_i64({"t": "int", "v": -(2 ** 63) - 1}) == -(2 ** 63) - 1
    assert first_out_of_i64({"t": "bool", "v": True}) is None
    assert first_out_of_i64({"t": "float", "v": 1e300}) is None
    assert first_out_of_i64({"t": "str", "v": "9" * 30}) is None
    nested = {"t": "list", "v": [{"t": "int", "v": 1}, {"t": "int", "v": 2 ** 70}]}
    assert first_out_of_i64(nested) == 2 ** 70
    d = {"t": "dict", "v": {"k": {"t": "tuple", "v": [{"t": "int", "v": 2 ** 64}]}}}
    assert first_out_of_i64(d) == 2 ** 64
