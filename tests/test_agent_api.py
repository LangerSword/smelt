"""Agent API (v0.8 plugin layer): handler core + detached job supervisor.

Hermetic: jobs use the fake provider with fixture candidates (no model, no
network). The env-allowlist test plants fake secrets and asserts they never
reach a child. Job dirs live under a temp SMELT_JOBS_DIR.
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from smelt_rs import agent_api as A  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures" / "candidates"
TARGET = str(REPO / "examples/demo/run_length.py:rle_encode")


@pytest.fixture(autouse=True)
def _jobs_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("SMELT_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("SMELT_BIN", str(REPO / ".venv/bin/smelt"))
    yield


def test_child_env_allowlist_never_leaks_foreign_secrets(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-aws")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake-discord")
    monkeypatch.setenv("SOME_PASSWORD", "fake-pw")
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nvidia")
    monkeypatch.setenv("SMELT_MODEL", "some-model")
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))
    env, dropped = A.child_environment()
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "DISCORD_BOT_TOKEN" not in env
    assert "SOME_PASSWORD" not in env
    assert env["NVIDIA_API_KEY"] == "fake-nvidia"      # smelt resolves this one
    assert env["SMELT_MODEL"] == "some-model"          # SMELT_* config passes
    assert "AWS_SECRET_ACCESS_KEY" in dropped and "DISCORD_BOT_TOKEN" in dropped
    assert all(isinstance(d, str) for d in dropped)    # names only, never values


def test_scan_bad_input_is_data():
    out = A.dispatch("smelt_scan", {})
    assert out["ok"] is False and "error" in out
    out = A.dispatch("smelt_scan", {"path": "/nonexistent-dir-xyz"})
    assert out["ok"] is False


def test_scan_real_roundtrip(tmp_path):
    (tmp_path / "demo.py").write_text("def shout(s: str) -> str:\n    return s.upper()\n")
    out = A.h_scan({"path": str(tmp_path)})
    assert out["ok"], out
    assert any(c["function"] == "shout" and c["status"] == "candidate"
               for c in out["candidates"])


def test_unknown_tool_is_data():
    out = A.dispatch("smelt_nope", {})
    assert out["ok"] is False and "unknown tool" in out["error"]


def _wait_done(job_id, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = A.h_job({"job_id": job_id})
        if st["state"] in ("done", "lost"):
            return st
        time.sleep(1)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


def test_detached_job_lifecycle(tmp_path):
    runs = tmp_path / "runs"
    out = A.h_run({"target": TARGET, "provider": "fake",
                   "candidate": str(FIXTURES / "rle_encode_correct.rs"),
                   "runs_dir": str(runs), "cases": 60})
    assert out["ok"], out
    job_id = out["job_id"]
    assert out["pid"] > 0
    # the call returned immediately; the job is running or already done
    st = _wait_done(job_id)
    assert st["state"] == "done", st
    assert st["exit_code"] == 0, st
    assert st["run"]["status"] == "accepted", st
    # verify: fresh terminal artifacts
    v = A.h_verify({"job_id": job_id})
    assert v["ok"], v
    assert v["run_dir"] and os.path.isdir(v["run_dir"])
    # report + apply read the same run
    rep = A.h_report({"run_dir": v["run_dir"]})
    assert rep["ok"] and "ACCEPTED" in rep["report"].upper()
    ap = A.h_apply({"run_dir": v["run_dir"]})
    assert ap["ok"] and ap["view_only"] and "+++ rust/" in ap["diff"]
    # jobs listing, newest first
    jobs = A.h_jobs({})
    assert jobs["ok"] and jobs["jobs"][0]["job_id"] == job_id
    # log tail works
    st2 = A.h_job({"job_id": job_id, "tail": 5})
    assert st2["log_tail"]
    # kill on a finished job is a no-op, not an error
    k = A.h_kill({"job_id": job_id})
    assert k["ok"] and k.get("already") == "done"


def test_job_repair_evidence_visible(tmp_path):
    """wrong -> correct via the fake provider: the job's run must show the
    repair attempt (schema-2 events) and still end accepted."""
    cands = tmp_path / "cands"
    cands.mkdir()
    (cands / "01_wrong.rs").write_text((FIXTURES / "rle_encode_wrong.rs").read_text())
    (cands / "02_correct.rs").write_text((FIXTURES / "rle_encode_correct.rs").read_text())
    out = A.h_run({"target": TARGET, "provider": "fake",
                   "candidate": str(cands / "*.rs"),
                   "runs_dir": str(tmp_path / "runs"), "cases": 60})
    st = _wait_done(out["job_id"])
    assert st["exit_code"] == 0, st
    events = [json.loads(l) for l in
              (Path(st["run_dir"]) / "events.jsonl").read_text().splitlines()]
    assert any(e["event"] == "repair" for e in events)


def test_verify_rejects_stale_artifacts(tmp_path):
    # fabricate a job whose run artifacts predate the job start
    jd = Path(A.jobs_root()) / "fakejob"
    jd.mkdir(parents=True)
    run_dir = tmp_path / "oldrun"
    run_dir.mkdir()
    for name in ("state.json", "report.md", "events.jsonl"):
        (run_dir / name).write_text("{}" if name.endswith("json") else "x")
    old = time.time() - 3600
    for name in ("state.json", "report.md", "events.jsonl"):
        os.utime(run_dir / name, (old, old))
    (jd / "meta.json").write_text(json.dumps(
        {"job_id": "fakejob", "target": TARGET, "started": time.time(),
         "pid": 999999, "runs_dir": str(tmp_path), "provider": "fake", "model": "-"}))
    (jd / "exit_code").write_text("0")
    (jd / "log.txt").write_text(json.dumps({"run_dir": str(run_dir)}) + "\n")
    v = A.h_verify({"job_id": "fakejob"})
    assert v["ok"] is False
    assert any("stale" in p for p in v["problems"]), v


def test_kill_and_job_bad_ids():
    assert A.h_kill({"job_id": "../escape"})["ok"] is False
    assert A.h_job({"job_id": "no-such-job"})["ok"] is False
    assert A.h_verify({"job_id": ""})["ok"] is False
