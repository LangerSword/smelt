"""list[float] widening (v0.8) — acceptance, rejection, scan, oracle edges.

Meta-eval-first discipline: the WRONG_FLOATLIST battery in scripts/meta_eval.py
was committed and observed RED (typed refusals) before support landed; after
support every wrong candidate must be rejected ON MERITS (exit 4). These tests
assert the stable invariants — acceptance itself is machine-dependent.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from smelt_rs.core import orchestrator  # noqa: E402
from smelt_rs import scan as scan_mod  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures" / "candidates"
TARGET = str(REPO / "examples/demo/rms.py:rms")


def _run(candidate, tmp_path, cases=200):
    return orchestrator.run(target=TARGET, provider_name="file", candidate=str(candidate),
                            runs_dir=str(tmp_path / "runs"), max_attempts=1,
                            target_cases=cases, quiet=True)


def test_rms_correct_verifies(tmp_path):
    code, info = _run(FIXTURES / "rms_correct.rs", tmp_path)
    reason = info.get("stop_reason") or ""
    assert code in (0, 4), reason
    assert "verify_mismatch" not in reason, reason
    if code == 4:
        assert ("reject_no_meaningful_gain" in reason
                or "reject_regression" in reason), reason


def test_rms_wrong_value_rejected(tmp_path):
    wrong = tmp_path / "wrong.rs"
    wrong.write_text((FIXTURES / "rms_correct.rs").read_text()
                     .replace("xs.iter().map(|x| x * x).sum()",
                              "xs.iter().map(|x| x.abs()).sum()")
                     .replace("Ok((s / xs.len() as f64).sqrt())",
                              "Ok(s / xs.len() as f64)"))
    code, info = _run(wrong, tmp_path)
    assert code == 4, info.get("stop_reason")
    assert "verify_mismatch" in (info.get("stop_reason") or ""), info


def test_rms_empty_edge_records_exception(tmp_path):
    code, info = orchestrator.capture_only(target=TARGET, runs_dir=str(tmp_path / "runs"),
                                           target_cases=200, quiet=True)
    assert code == 0, info
    assert info["oracle"]["n_cases"] >= 200
    oracle = Path(info["run_dir"]) / "oracle" / "oracle.jsonl"
    entries = [json.loads(l) for l in oracle.read_text().splitlines()]
    empty = [e for e in entries if e["args"] == [[]]]
    assert empty, "the empty-list edge must be in the oracle"
    assert all(e["expected_ok"] is False for e in empty), "empty input raises ValueError"


def test_raising_target_reaches_bench(tmp_path):
    """Regression (v0.8): targets that raise on edge cases (rms: empty list)
    must reach bench — before the fix, time_once died on the raising case and
    the run halted as bench_insufficient despite a 100% verified rewrite."""
    code, info = _run(FIXTURES / "rms_correct.rs", tmp_path)
    reason = info.get("stop_reason") or ""
    assert code in (0, 4), reason
    assert "bench_insufficient" not in reason, reason
    assert "verify_mismatch" not in reason, reason
    if code == 4:
        assert ("reject_no_meaningful_gain" in reason
                or "reject_regression" in reason), reason


def test_divide_out_of_domain_edge_now_refused_at_capture(tmp_path):
    """divide's edge battery includes (i64::MIN, -1) -> 2**63, beyond i64.
    Pre-v0.8 this burned a build and surfaced as verify_mismatch; the domain
    guard now refuses it at capture (exit 3) with a hint — no provider calls."""
    code, info = orchestrator.run(
        target=str(REPO / "examples/demo/divide.py:divide"),
        provider_name="file", candidate=str(FIXTURES / "divide_correct.rs"),
        runs_dir=str(tmp_path / "runs"), max_attempts=1, target_cases=200, quiet=True)
    assert code == 3, info
    assert "i64 domain" in (info.get("stop_reason") or ""), info


def test_scan_lists_float_list_candidate(tmp_path):
    f = tmp_path / "fl.py"
    f.write_text("def mean(xs: list[float]) -> float:\n    return sum(xs) / len(xs)\n")
    res = scan_mod.scan_path(str(tmp_path))
    e = res["candidates"][0]
    assert e["status"] == "candidate", e
    assert e["param"] == "list[float]"
