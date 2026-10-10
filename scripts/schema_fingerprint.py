#!/usr/bin/env python
"""Build/check the events.jsonl schema fingerprint.

The fingerprint records, for every event type the emitter can write, the exact
set of fields it writes. Any change to the emitter's field sets or event list
shows up as a fingerprint mismatch, forcing a deliberate EVENT_SCHEMA_VERSION
bump plus a fingerprint regeneration. This is how tests fail when the schema
changes without a version bump.

Regenerate (after a deliberate, versioned change):
    python scripts/schema_fingerprint.py --write
Check manually:
    python scripts/schema_fingerprint.py --check
"""
import argparse
import importlib.util
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINGERPRINT_PATH = os.path.join(ROOT, "tests", "fixtures", "events", "schema_fingerprint.json")

# One representative payload per event type, mirroring the real call sites in
# src/smelt_rs/core/orchestrator.py exactly (same keyword arguments).
SAMPLES = [
    ("run_start", {"target": "a.py:fn", "provider": "file", "model": "-"}),
    ("purity_ok", {}),
    ("capture_done", {"n_cases": 85, "sha256": "0" * 16}),
    ("attempt_start", {"attempt": 1}),
    ("resume", {"from_attempt": 2}),
    ("safety_violation", {"attempt": 1}),
    ("build_error", {"attempt": 1, "subkind": "compile_error"}),
    ("verify_mismatch", {"attempt": 1, "n_bad": 3}),
    ("accept", {"ratio": 2.0, "ratio_ci_lo": 1.8, "flags": []}),
    ("reject_no_meaningful_gain", {"ratio": 1.2}),
    ("halt", {"kind": "capture_failed", "message": "x"}),
    ("run_end", {"status": "accepted", "reason": "ok"}),
]


def _state_module():
    spec = importlib.util.spec_from_file_location(
        "smelt_state", os.path.join(ROOT, "src", "smelt_rs", "core", "state.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_fingerprint() -> dict:
    st = _state_module()
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "e.jsonl")
        log = st.EventLog(p)
        for event, payload in SAMPLES:
            log.emit(event, **payload)
        recs = [json.loads(line) for line in open(p)]
    common = sorted(set(recs[0].keys()) - {"event"})
    events = {}
    for rec in recs:
        events[rec["event"]] = sorted(rec.keys())
    return {"version": st.EVENT_SCHEMA_VERSION, "common": common, "events": events}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write the fingerprint file")
    ap.add_argument("--check", action="store_true", help="compare and exit non-zero on mismatch")
    args = ap.parse_args()
    fp = build_fingerprint()
    if args.write:
        os.makedirs(os.path.dirname(FINGERPRINT_PATH), exist_ok=True)
        with open(FINGERPRINT_PATH, "w") as f:
            json.dump(fp, f, indent=2, sort_keys=True)
        print("wrote", os.path.relpath(FINGERPRINT_PATH, ROOT), "(version", fp["version"] + ")")
        return 0
    frozen = json.load(open(FINGERPRINT_PATH))
    if fp != frozen:
        print("FINGERPRINT MISMATCH — the emitted schema changed.")
        print("Bump EVENT_SCHEMA_VERSION in src/smelt_rs/core/state.py, update docs/events.md,")
        print("then rerun: python scripts/schema_fingerprint.py --write")
        for k in ("version", "common"):
            if fp.get(k) != frozen.get(k):
                print(f"  {k}: live={fp.get(k)} frozen={frozen.get(k)}")
        live_e, frozen_e = fp.get("events", {}), frozen.get("events", {})
        for name in sorted(set(live_e) | set(frozen_e)):
            if live_e.get(name) != frozen_e.get(name):
                print(f"  {name}: live={live_e.get(name)} frozen={frozen_e.get(name)}")
        return 1
    print("fingerprint OK (version", fp["version"] + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
