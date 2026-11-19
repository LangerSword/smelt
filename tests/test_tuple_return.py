"""Tuple RETURNS (v0.8) — return-container fidelity.

Meta-eval-first: g02_list_not_tuple was observed passing verify pre-fix (it was
rejected only by the speed threshold — a machine-dependent false-accept hole).
With the tuple tag in the oracle + verifier it must be rejected ON MERITS
(verify_mismatch) on every machine. That rejection is a stable invariant and IS
asserted here; acceptance of the correct candidate remains machine-dependent.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from smelt_rs.core import orchestrator  # noqa: E402
from smelt_rs.oracle.verify import values_equal  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures" / "candidates"
TARGET = str(REPO / "examples/demo/sum_pair.py:sum_pair")


def _run(candidate, tmp_path, cases=200):
    return orchestrator.run(target=TARGET, provider_name="file", candidate=str(candidate),
                            runs_dir=str(tmp_path / "runs"), max_attempts=1,
                            target_cases=cases, quiet=True)


def test_sum_pair_correct_verifies(tmp_path):
    code, info = _run(FIXTURES / "sum_pair_correct.rs", tmp_path)
    reason = info.get("stop_reason") or ""
    assert code in (0, 4), reason
    assert "verify_mismatch" not in reason, reason
    if code == 4:
        assert ("reject_no_meaningful_gain" in reason
                or "reject_regression" in reason), reason


def test_list_return_rejected_on_type_not_speed(tmp_path):
    """The fidelity gate: identical elements, wrong container -> verify_mismatch.
    Stable across machines — unlike the pre-fix behavior, where this candidate
    passed verify and was only stopped by the 1.5x threshold."""
    wrong = tmp_path / "list_ret.rs"
    wrong.write_text((FIXTURES / "sum_pair_correct.rs").read_text()
                     .replace("fn sum_pair(xs: Vec<i64>) -> (i64, i64) {",
                              "fn sum_pair(xs: Vec<i64>) -> Vec<i64> {")
                     .replace("    (s, q)\n}", "    vec![s, q]\n}"))
    code, info = _run(wrong, tmp_path)
    assert code == 4, info.get("stop_reason")
    assert "verify_mismatch" in (info.get("stop_reason") or ""), info


def test_oracle_records_tuple_tag(tmp_path):
    code, info = orchestrator.capture_only(target=TARGET, runs_dir=str(tmp_path / "runs"),
                                           target_cases=200, quiet=True)
    assert code == 0, info
    oracle = Path(info["run_dir"]) / "oracle" / "oracle.jsonl"
    entries = [json.loads(l) for l in oracle.read_text().splitlines()]
    assert entries and all(e["expected"]["t"] == "tuple" for e in entries if e["expected_ok"])


def test_typing_tuple_annotation_normalized(tmp_path):
    f = tmp_path / "tt.py"
    f.write_text("from typing import Tuple\n\n\n"
                 "def pair(xs: list[int]) -> Tuple[int, int]:\n"
                 "    return (sum(xs), len(xs))\n")
    code, info = orchestrator.capture_only(target=f"{f}:pair",
                                           runs_dir=str(tmp_path / "runs"),
                                           target_cases=60, quiet=True)
    assert code == 0, info
    assert info["oracle"]["n_cases"] >= 60


def test_values_equal_container_fidelity_unit():
    t = {"t": "tuple", "v": [{"t": "int", "v": 1}, {"t": "int", "v": 2}]}
    l = {"t": "list", "v": [{"t": "int", "v": 1}, {"t": "int", "v": 2}]}
    assert values_equal(t, json.loads(json.dumps(t))) is True
    assert values_equal(t, l) is False, "tuple != list even with identical elements"
    assert values_equal(l, t) is False
    nested_t = {"t": "tuple", "v": [l]}
    nested_l = {"t": "list", "v": [l]}
    assert values_equal(nested_t, nested_l) is False
