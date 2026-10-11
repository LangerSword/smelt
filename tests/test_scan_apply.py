"""Tests for the minimal scan/apply (Furnace T3 prerequisites)."""

import json
import os

from smelt_rs import apply as apply_mod
from smelt_rs import scan as scan_mod


def _write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def test_scan_classifies(tmp_path):
    root = tmp_path / "proj"
    _write(str(root / "pure_ok.py"), "def shout(s: str) -> str:\n    return s.upper()\n")
    _write(str(root / "impure.py"),
           "import random\n\n\ndef pick(vals: list[int]) -> int:\n    return random.choice(vals)\n")
    _write(str(root / "pkg" / "__init__.py"), "")
    _write(str(root / "pkg" / "mod.py"),
           "from . import nothing  # noqa\n\n\ndef f(s: str) -> str:\n    return s\n")
    _write(str(root / "multi.py"), "def add(a: int, b: int) -> int:\n    return a + b\n")
    _write(str(root / "unannotated.py"), "def who(x):\n    return x\n")
    res = scan_mod.scan_path(str(root))
    by = {(c["file"], c["function"]): c for c in res["candidates"]}

    assert by[("pure_ok.py", "shout")]["status"] == "candidate"
    assert by[("pure_ok.py", "shout")]["param"] == "str"

    assert by[("impure.py", "pick")]["status"] == "skip"
    assert by[("impure.py", "pick")]["tier"] == "refused"
    assert "impure" in by[("impure.py", "pick")]["reason"]

    assert by[("pkg/mod.py", "f")]["status"] == "skip"
    assert "relative imports" in by[("pkg/mod.py", "f")]["reason"]

    # G1/G3 widening: several simple positional parameters are now supported
    assert by[("multi.py", "add")]["status"] == "candidate"
    assert by[("multi.py", "add")]["tier"] == "1"
    assert "2 simple parameters" in by[("multi.py", "add")]["reason"]

    assert by[("unannotated.py", "who")]["status"] == "skip"
    assert "unsupported parameter type" in by[("unannotated.py", "who")]["reason"]

    assert res["summary"]["candidates"] == 2  # shout + add


def test_scan_keyword_only_refused(tmp_path):
    root = tmp_path / "proj2"
    _write(str(root / "kw.py"),
           "def f(value: str, *, flag: bool = False) -> str:\n    return value\n")
    res = scan_mod.scan_path(str(root))
    entry = res["candidates"][0]
    assert entry["status"] == "skip"
    assert entry["tier"] == "refused"
    assert "keyword-only" in entry["reason"]


def test_scan_examples_has_rle_candidate():
    res = scan_mod.scan_path("examples")
    cands = [c for c in res["candidates"] if c["status"] == "candidate"]
    assert any(c["function"] == "rle_encode" for c in cands)


def test_apply_view_only_output(tmp_path, capsys):
    rd = tmp_path / "run"
    _write(str(rd / "state.json"), json.dumps({
        "run_id": "r1", "status": "accepted",
        "target": {"path": "x.py", "qualname": "f"},
        "attempts": [{"bench": "2.0x (lb 1.8x)"}],
    }))
    _write(str(rd / "attempts" / "it1" / "lib.rs"),
           "use pyo3::prelude::*;\n\n#[pyfunction]\nfn f(s: &str) -> String { s.to_string() }\n")
    rc = apply_mod.apply(str(rd))
    out = capsys.readouterr().out
    assert rc == 0
    assert "VIEW ONLY" in out
    assert "+++ rust/f/src/lib.rs" in out
    assert "except Exception" in out
    assert "+fn f(s: &str) -> String" in out


def test_apply_refuses_non_accepted(tmp_path, capsys):
    rd = tmp_path / "run2"
    _write(str(rd / "state.json"), json.dumps({
        "run_id": "r2", "status": "rejected", "target": {}, "attempts": [],
    }))
    rc = apply_mod.apply(str(rd))
    err = capsys.readouterr().err
    assert rc == 4
    assert "nothing to apply" in err
