"""Pin the events.jsonl schema.

Any change to the emitter's event list or field sets fails these tests until
EVENT_SCHEMA_VERSION is bumped AND the fingerprint is regenerated
(`python scripts/schema_fingerprint.py --write`). The golden fixture is a real
run's stream, copied verbatim, so docs and tests stay anchored to real output.
"""
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(mod_name, rel):
    spec = importlib.util.spec_from_file_location(mod_name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


fp_mod = _load("schema_fingerprint", "scripts/schema_fingerprint.py")
state_mod = _load("smelt_state", "src/smelt_rs/core/state.py")

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "events", "schema_fingerprint.json")
GOLDEN = os.path.join(ROOT, "tests", "fixtures", "events", "golden_run.jsonl")
DOCS = os.path.join(ROOT, "docs", "events.md")


def test_emitter_matches_frozen_fingerprint():
    frozen = json.load(open(FIXTURE))
    live = fp_mod.build_fingerprint()
    assert live["common"] == frozen["common"], (
        "common fields changed — bump EVENT_SCHEMA_VERSION and regenerate the fingerprint "
        "(python scripts/schema_fingerprint.py --write)")
    assert live["events"] == frozen["events"], (
        "event schema changed — bump EVENT_SCHEMA_VERSION and regenerate the fingerprint "
        "(python scripts/schema_fingerprint.py --write)")


def test_fingerprint_version_tracks_constant():
    frozen = json.load(open(FIXTURE))
    assert frozen["version"] == state_mod.EVENT_SCHEMA_VERSION, (
        "fingerprint version != EVENT_SCHEMA_VERSION — regenerate the fingerprint after the bump")


def test_docs_match_emitted_event_list():
    text = open(DOCS).read()
    live = fp_mod.build_fingerprint()
    for t in live["events"]:
        assert f"`{t}`" in text, f"docs/events.md is missing event `{t}`"
    assert f'`{live["version"]}`' in text, "docs/events.md must state the current schema version"


def test_golden_real_run_stream_is_valid():
    lines = [l for l in open(GOLDEN) if l.strip()]
    assert lines, "golden fixture missing"
    recs = [json.loads(l) for l in lines]
    for rec in recs:
        assert rec["schema_version"] == state_mod.EVENT_SCHEMA_VERSION
        assert "ts" in rec and "node" in rec and "event" in rec
    assert recs[0]["event"] == "run_start"
    assert recs[-1]["event"] == "run_end"
