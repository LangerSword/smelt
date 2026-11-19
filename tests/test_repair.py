"""Repair loop (v0.8): attempts 2+ receive EVIDENCE from the failed attempt.

The gates never change — these tests prove the information flow, not acceptance:
accept/reject stays machine-dependent (measured speedup), so tests assert the
stable invariants (typed outcome, no mismatch for a correct candidate, evidence
present in the repair prompt, feedback checkpointed on disk).
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from smelt_rs.core import orchestrator  # noqa: E402
from smelt_rs.providers.providers import build_repair_prompt  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures" / "candidates"
TARGET = str(REPO / "examples/demo/run_length.py:rle_encode")


class RecordingProvider:
    """File-backed provider that records every prompt it is handed."""

    name = "fake"

    def __init__(self, paths):
        self.paths = [str(p) for p in paths]
        self.prompts: list[str] = []
        self.i = 0

    def generate(self, prompt: str, n: int = 1) -> list[str]:
        self.prompts.append(prompt)
        out = [open(p).read() for p in self.paths[self.i:self.i + n]]
        self.i += n
        return out


def _run_with(monkeypatch, tmp_path, candidates, repair=True, max_attempts=2):
    rec = RecordingProvider(candidates)
    monkeypatch.setattr(orchestrator, "make_provider", lambda *a, **k: rec)
    code, info = orchestrator.run(target=TARGET, provider_name="fake",
                                  runs_dir=str(tmp_path / "runs"),
                                  max_attempts=max_attempts, target_cases=60,
                                  quiet=True, repair=repair)
    run_dir = Path(info["run_dir"])
    return code, info, rec, run_dir


def test_mismatch_evidence_reaches_attempt_two(monkeypatch, tmp_path):
    code, info, rec, run_dir = _run_with(
        monkeypatch, tmp_path,
        [FIXTURES / "rle_encode_wrong.rs", FIXTURES / "rle_encode_correct.rs"])
    assert len(rec.prompts) == 2, info.get("stop_reason")
    # attempt 2 prompt carries the repair contract + concrete failing cases
    p2 = rec.prompts[1]
    assert "REPAIR" in p2
    assert "Previous attempt" in p2
    v1 = json.loads((run_dir / "attempts/it1/verify.json").read_text())
    assert v1["n_mismatch"] > 0
    first_bad = v1["sample"][0]["case_id"]
    assert first_bad in p2, "repair prompt must name a failing case"
    assert '"expected"' in p2 and '"got"' in p2
    # feedback checkpointed for audit + resume
    fb = json.loads((run_dir / "attempts/it2/feedback.json").read_text())
    assert fb["kind"] == "verify_mismatch"
    assert fb["n_bad"] == v1["n_mismatch"]
    # the correct candidate must verify — outcome is accept or honest no-gain
    assert code in (0, 4), info.get("stop_reason")
    reason = info.get("stop_reason") or ""
    assert "verify_mismatch" not in reason, reason
    if code == 4:
        assert ("reject_no_meaningful_gain" in reason
                or "reject_regression" in reason), reason
    # repair event emitted (schema v2)
    events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines()]
    assert any(e["event"] == "repair" and e["kind"] == "verify_mismatch" for e in events)


def test_no_repair_keeps_prompt_identical(monkeypatch, tmp_path):
    code, info, rec, run_dir = _run_with(
        monkeypatch, tmp_path,
        [FIXTURES / "rle_encode_wrong.rs", FIXTURES / "rle_encode_correct.rs"],
        repair=False)
    assert len(rec.prompts) == 2
    assert rec.prompts[0] == rec.prompts[1], "--no-repair must resend the base prompt"
    assert not (run_dir / "attempts/it2/feedback.json").exists()
    events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines()]
    assert not any(e["event"] == "repair" for e in events)


def test_build_error_evidence_reaches_attempt_two(monkeypatch, tmp_path):
    broken = tmp_path / "broken.rs"
    src = (FIXTURES / "rle_encode_correct.rs").read_text()
    # syntax error inside the body; still passes the static safety scan
    broken.write_text(src.replace("let mut out = String::new();",
                                  "let mut out = String::new()  // missing semicolon\n    let x: i64 = \"not an int\";"))
    code, info, rec, run_dir = _run_with(
        monkeypatch, tmp_path, [broken, FIXTURES / "rle_encode_correct.rs"])
    assert len(rec.prompts) == 2, info.get("stop_reason")
    p2 = rec.prompts[1]
    assert "REPAIR" in p2 and "compiler" in p2
    assert "error" in p2  # rustc diagnostic text made it into the prompt
    fb = json.loads((run_dir / "attempts/it2/feedback.json").read_text())
    assert fb["kind"] == "build_error"
    assert fb["stderr"].strip()
    assert code in (0, 4), info.get("stop_reason")
    assert "verify_mismatch" not in (info.get("stop_reason") or "")


def test_repair_prompt_unit_shapes():
    base = "BASE CONTRACT"
    huge = "x" * 30000
    for kind, marker in [("build_error", "compiler"), ("safety_violation", "safety scan"),
                         ("verify_mismatch", "oracle cases differ"), ("no_gain", "1.5x"),
                         ("load_error", "sandbox worker")]:
        fb = {"kind": kind, "candidate": huge, "stderr": "error[E0308]: mismatched types",
              "violations": ["banned pattern: unsafe block"], "n_bad": 3, "n_cases": 85,
              "sample": [{"case_id": "e0001", "args": ["aa"], "expected": {"t": "str", "v": "a2"},
                          "got": {"t": "str", "v": "a1"}}],
              "ratio": 1.2, "ratio_ci_lo": 1.1, "error": "ImportError: boom"}
        p = build_repair_prompt(base, fb)
        assert p.startswith(base)
        assert marker in p, kind
        assert len(p) < 30000, "candidate must be capped"
    # unknown kind still renders the contract + previous attempt (no crash)
    p = build_repair_prompt(base, {"kind": "mystery", "candidate": "fn f() {}"})
    assert "REPAIR" in p and "fn f() {}" in p


def test_file_provider_advances_and_wraps(tmp_path):
    from smelt_rs.providers.providers import FileProvider
    a, b = tmp_path / "a.rs", tmp_path / "b.rs"
    a.write_text("A")
    b.write_text("B")
    p = FileProvider([str(a), str(b)])
    assert p.generate("p", n=1) == ["A"]
    assert p.generate("p", n=1) == ["B"], "attempt 2 must see candidate 2"
    assert p.generate("p", n=1) == ["A"], "exhausted list wraps (single-candidate gate runs unchanged)"
    single = FileProvider([str(a)])
    assert single.generate("p") == ["A"] and single.generate("p") == ["A"]


def test_resume_reconstructs_mismatch_feedback(tmp_path):
    run_dir = tmp_path / "runs" / "x"
    ad = run_dir / "attempts" / "it1"
    ad.mkdir(parents=True)
    (ad / "lib.rs").write_text("fn rle_encode() {}")
    (ad / "verify.json").write_text(json.dumps(
        {"n_cases": 85, "n_mismatch": 4, "sample": [{"case_id": "e0002"}]}))

    class St:
        attempts = [{"attempt": 1, "outcome": "verify_mismatch: e0002 output differs"}]

    fb = orchestrator._reconstruct_feedback(str(run_dir), St())
    assert fb is not None and fb["kind"] == "verify_mismatch"
    assert fb["n_bad"] == 4 and fb["sample"][0]["case_id"] == "e0002"
    assert "rle_encode" in fb["candidate"]
    # no evidence on disk -> no fabricated feedback
    (ad / "verify.json").unlink()
    assert orchestrator._reconstruct_feedback(str(run_dir), St()) is None
