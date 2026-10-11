"""Step-1 fixes from the blind test: typed refusals + clear messages, no crashes.

Covers the three findings in evals/general.md:
- BUG-1: package files (relative imports) must surface the real error, not
  "no parameters";
- BUG-2: a not-found / dotted qualname is a config error (exit 2), not an
  impurity refusal;
- BUG-3: unsupported parameter shapes are typed refusals (exit 3) with a
  reason and a refactor hint.
"""

import os

from smelt_rs.core import orchestrator


def _write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def _run(tmp_path, path, func):
    return orchestrator.run(target=f"{path}:{func}", provider_name="file", model=None,
                            runs_dir=str(tmp_path / "runs"), max_attempts=1,
                            target_cases=20, quiet=True)


def test_relative_import_surfaces_real_error(tmp_path):
    pkg = tmp_path / "pkg"
    _write(str(pkg / "__init__.py"), "")
    _write(str(pkg / "mod.py"), "from . import sibling  # noqa\n\n\ndef f(s: str) -> str:\n    return s\n")
    code, info = _run(tmp_path, str(pkg / "mod.py"), "f")
    assert code == 3, info
    reason = info["stop_reason"]
    assert "no parameters" not in reason
    assert "relative import" in reason or "could not load" in reason
    assert "hint" in reason


def test_dotted_qualname_is_config_error(tmp_path):
    f = tmp_path / "c.py"
    _write(str(f), "class C:\n    def m(self, s: str) -> str:\n        return s\n")
    code, info = _run(tmp_path, str(f), "C.m")
    assert code == 2, info
    reason = info.get("stop_reason") or info.get("reason", "")
    assert "not found" in reason
    assert "dotted" in reason


def test_multi_param_now_captures(tmp_path):
    """G1 widening: two-parameter targets are supported — the oracle freezes them.

    (Previously a typed refusal; the meta-eval multi-param battery plus the
    divide_correct.rs accept are the end-to-end gates.)"""
    import glob
    import json
    from smelt_rs.core import orchestrator
    src = tmp_path / "m.py"
    _write(str(src), "def add(a: int, b: int) -> int:\n    return a + b\n")
    code, info = orchestrator.capture_only(target=f"{src}:add",
                                           runs_dir=str(tmp_path / "runs"),
                                           target_cases=60, quiet=True)
    assert code == 0, info
    run_dir = sorted(glob.glob(str(tmp_path / "runs" / "*")))[-1]
    meta = json.load(open(os.path.join(run_dir, "oracle", "meta.json")))
    assert len(meta["params"]) == 2
    assert meta["n_cases"] >= 40


def test_unsupported_type_is_typed_refusal(tmp_path):
    f = tmp_path / "u.py"
    _write(str(f), "from typing import Iterable\n\n\ndef first(xs: Iterable[int]) -> int:\n    return next(iter(xs))\n")
    code, info = _run(tmp_path, str(f), "first")
    assert code == 3, info
    assert "unsupported parameter type" in info["stop_reason"]
    assert "hint" in info["stop_reason"]


def test_exit_code_map():
    from smelt_rs.core.orchestrator import _exit_for_kind
    assert _exit_for_kind("refused_impure") == 3
    assert _exit_for_kind("refused_unsupported_target") == 3
    assert _exit_for_kind("config_error") == 2
    assert _exit_for_kind("build_error") == 5
