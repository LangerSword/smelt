"""Package-layout support (v0.8, BUG-1 fix).

Targets inside packages with relative imports must load in their package
context, verify against the oracle exactly like standalone targets, and be
listed by scan. Unresolvable relative imports stay typed refusals — never
crashes, never false accepts. Acceptance is machine-dependent (measured), so
tests assert the stable invariants only.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from smelt_rs.core import orchestrator  # noqa: E402
from smelt_rs import scan as scan_mod  # noqa: E402

PKG = REPO / "tests" / "fixtures" / "pkgdemo"
FIXTURES = REPO / "tests" / "fixtures" / "candidates"


def _run(target, candidate, tmp_path, cases=200):
    return orchestrator.run(target=target, provider_name="file", candidate=str(candidate),
                            runs_dir=str(tmp_path / "runs"), max_attempts=1,
                            target_cases=cases, quiet=True)


def test_package_target_verifies(tmp_path):
    code, info = _run(str(PKG / "textutil.py:sum_doubled"),
                      FIXTURES / "sum_doubled_correct.rs", tmp_path)
    reason = info.get("stop_reason") or ""
    assert code in (0, 4), reason
    assert "verify_mismatch" not in reason, reason
    assert "could not load" not in reason, reason
    if code == 4:
        assert ("reject_no_meaningful_gain" in reason
                or "reject_regression" in reason), reason


def test_nested_package_level2_import_verifies(tmp_path):
    code, info = _run(str(PKG / "sub" / "deep.py:sum_doubled_deep"),
                      FIXTURES / "sum_doubled_deep_correct.rs", tmp_path)
    reason = info.get("stop_reason") or ""
    assert code in (0, 4), reason
    assert "verify_mismatch" not in reason, reason
    assert "could not load" not in reason, reason


def test_wrong_package_rewrite_rejected(tmp_path):
    wrong = tmp_path / "wrong.rs"
    wrong.write_text((FIXTURES / "sum_doubled_correct.rs").read_text()
                     .replace("xs.iter().map(|x| x * 2).sum()", "xs.iter().sum()"))
    code, info = _run(str(PKG / "textutil.py:sum_doubled"), wrong, tmp_path)
    assert code == 4, info.get("stop_reason")
    assert "verify_mismatch" in (info.get("stop_reason") or ""), info


def test_capture_only_package(tmp_path):
    code, info = orchestrator.capture_only(target=str(PKG / "textutil.py:sum_doubled"),
                                           runs_dir=str(tmp_path / "runs"),
                                           target_cases=200, quiet=True)
    assert code == 0, info
    assert info["oracle"]["n_cases"] >= 200


def test_scan_lists_package_candidates():
    res = scan_mod.scan_path(str(PKG))
    by = {(c["file"], c["function"]): c for c in res["candidates"]}
    e = by[("textutil.py", "sum_doubled")]
    assert e["status"] == "candidate", e
    assert e.get("package") is True
    d = by[("sub/deep.py", "sum_doubled_deep")]
    assert d["status"] == "candidate", d


def test_broken_relative_import_is_typed_refusal(tmp_path):
    pkg = tmp_path / "brokenpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("from . import missing\n\n\n"
                                "def f(xs: list[int]) -> int:\n    return sum(xs)\n")
    code, info = orchestrator.run(target=str(pkg / "mod.py:f"), provider_name="file",
                                  candidate=str(FIXTURES / "sum_doubled_correct.rs"),
                                  runs_dir=str(tmp_path / "runs"), max_attempts=1,
                                  target_cases=60, quiet=True)
    assert code == 3, info
    assert info["status"] == "refused", info
    assert "could not load" in (info.get("stop_reason") or ""), info
