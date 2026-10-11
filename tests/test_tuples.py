"""Tuple widening (tuple[int, int]) — acceptance, rejection, coercion, scan.

The coercion proof: the oracle records `isinstance(p, tuple)` for a tuple-annotated
parameter. JSON has no tuples, so a 2-element list arrives unless the worker
converts it back. `is_tuple_correct.rs` always returns true — it can only be
ACCEPTED if the Python side recorded true, i.e. if coercion works on both sides.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from smelt_rs.core import orchestrator  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures" / "candidates"


def _run(target: str, candidate, tmp_path: Path, cases: int = 200):
    return orchestrator.run(target=target, provider_name="file", candidate=str(candidate),
                            runs_dir=str(tmp_path / "runs"), max_attempts=1,
                            target_cases=cases, quiet=True)


def test_gcd_pair_tuple_accepted(tmp_path):
    """Accept proof for the tuple path: a loop-heavy tuple target wins."""
    code, info = _run(str(REPO / "examples/demo/gcd_pair.py:gcd_pair"),
                      FIXTURES / "gcd_pair_correct.rs", tmp_path)
    assert code == 0, info.get("stop_reason")
    assert "verified" in (info.get("stop_reason") or "")


def test_manhattan_verifies_but_honest_reject(tmp_path):
    """manhattan verifies on every case (reaches bench) and is honestly rejected
    for gain (1.43x < 1.5x rule) — tiny functions cannot beat pyo3 overhead."""
    code, info = _run(str(REPO / "examples/demo/manhattan.py:manhattan"),
                      FIXTURES / "manhattan_correct.rs", tmp_path)
    assert code == 4, info.get("stop_reason")
    assert "reject_no_meaningful_gain" in (info.get("stop_reason") or ""), info


def test_wrong_tuple_rewrite_rejected(tmp_path):
    wrong = tmp_path / "wrong.rs"
    wrong.write_text((FIXTURES / "manhattan_correct.rs").read_text()
                     .replace("p.0.abs() + p.1.abs()", "p.0 + p.1"))
    code, info = _run(str(REPO / "examples/demo/manhattan.py:manhattan"), wrong, tmp_path)
    assert code == 4, info.get("stop_reason")
    assert "verify_mismatch" in (info.get("stop_reason") or ""), info


def test_coercion_proven_by_isinstance(tmp_path):
    """The oracle records `isinstance(p, tuple)`; JSON has no tuples, so this is
    True only when the worker converts the 2-element list back. Read the oracle
    directly — no bench involved."""
    target = tmp_path / "is_tuple.py"
    target.write_text("def is_tuple(p: tuple[int, int]) -> bool:\n"
                      "    return isinstance(p, tuple)\n")
    code, info = orchestrator.capture_only(target=f"{target}:is_tuple",
                                           runs_dir=str(tmp_path / "runs2"),
                                           target_cases=120, quiet=True)
    assert code == 0, info
    import json as _json
    oracle_dir = Path(info["run_dir"]) / "oracle" if "run_dir" in info else None
    if oracle_dir is None:
        runs = sorted((tmp_path / "runs2").glob("*"))
        oracle_dir = runs[-1] / "oracle"
    entries = [_json.loads(l) for l in (oracle_dir / "oracle.jsonl").read_text().splitlines()]
    assert entries and all(e["expected"] == {"t": "bool", "v": True} for e in entries), entries[:2]


def test_scan_tier1_for_tuple():
    from smelt_rs import scan
    out = scan.scan_path(str(REPO / "examples" / "demo"))
    entry = next(e for e in out["candidates"] if e.get("function") == "manhattan")
    assert entry.get("tier") == "1", entry
    assert "tuple" in (entry.get("param") or ""), entry
