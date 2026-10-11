"""Launcher tests: bare `smelt` must launch the Furnace TUI.

The TUI binary is resolved SMELT_FURNACE_BIN → PATH → repo tui/furnace.
These tests never need a real TUI: a stub shell script stands in for it.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run_cli(args, env_extra):
    env = os.environ.copy()
    env.update(env_extra)
    return subprocess.run([sys.executable, "-m", "smelt_rs.cli", *args],
                          capture_output=True, text=True, timeout=20, env=env,
                          cwd=str(REPO))


def test_bare_smelt_execs_furnace(tmp_path):
    fake = tmp_path / "furnace"
    fake.write_text("#!/bin/sh\necho FURNACE_LAUNCHED\n")
    fake.chmod(0o755)
    r = _run_cli([], {"SMELT_FURNACE_BIN": str(fake)})
    assert r.returncode == 0, r.stderr
    assert "FURNACE_LAUNCHED" in r.stdout


def test_find_furnace_none(monkeypatch, tmp_path):
    from smelt_rs import cli
    monkeypatch.delenv("SMELT_FURNACE_BIN", raising=False)
    monkeypatch.setattr(cli.shutil, "which", lambda _n: None)
    assert cli._find_furnace(root=str(tmp_path)) is None


def test_find_furnace_env_override(monkeypatch, tmp_path):
    from smelt_rs import cli
    fake = tmp_path / "fx"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("SMELT_FURNACE_BIN", str(fake))
    assert cli._find_furnace() == str(fake)


def test_smelt_help_still_works():
    r = _run_cli(["--help"], {})
    assert r.returncode == 0, r.stderr
    assert "Usage:" in r.stdout


def test_smelt_subcommand_still_works():
    # `smelt scan` must not launch the TUI even when one is resolvable.
    r = _run_cli(["scan", "examples/demo"], {"SMELT_FURNACE_BIN": "/bin/true"})
    assert r.returncode == 0, r.stderr
    assert "candidate" in r.stdout
