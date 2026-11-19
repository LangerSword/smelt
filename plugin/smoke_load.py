#!/usr/bin/env python3
"""Served-surface proof for the smelt Hermes plugin — no Hermes install needed.

Loads plugin/__init__.py as a package, registers against a recording ctx,
asserts declared == registered (tools + hooks), dispatches pre_tool_call with
real payloads (mutating -> approve card, read-only -> None), and drives one
real handler (scan on a temp dir) to confirm it answers as data.

Run: python3 plugin/smoke_load.py
"""

import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


class RecordingCtx:
    def __init__(self):
        self.tools = {}
        self.hooks = {}

    def register_tool(self, name, toolset, schema, handler, description, emoji=None):
        self.tools[name] = {"toolset": toolset, "schema": schema,
                            "handler": handler, "description": description}

    def register_hook(self, name, fn):
        self.hooks.setdefault(name, []).append(fn)


def load_plugin():
    spec = importlib.util.spec_from_file_location(
        "smelt_plugin", os.path.join(HERE, "__init__.py"),
        submodule_search_locations=[HERE])
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["smelt_plugin"] = mod
    spec.loader.exec_module(mod)
    return mod


def declared_names() -> tuple[list[str], list[str]]:
    """Read provides_tools / provides_hooks from plugin.yaml (stdlib parse)."""
    text = open(os.path.join(HERE, "plugin.yaml")).read()
    tools, hooks = [], []
    section = None
    for line in text.splitlines():
        if line.startswith("provides_tools:"):
            section = tools
        elif line.startswith("provides_hooks:"):
            section = hooks
        elif line and not line[0].isspace():
            section = None
        elif section is not None:
            m = re.match(r"\s+-\s+(\S+)", line)
            if m:
                section.append(m.group(1))
    return tools, hooks


def main() -> int:
    failures = []
    mod = load_plugin()
    ctx = RecordingCtx()
    mod.register(ctx)

    want_tools, want_hooks = declared_names()
    if sorted(ctx.tools) != sorted(want_tools):
        failures.append(f"tools declared {want_tools} != registered {sorted(ctx.tools)}")
    if sorted(ctx.hooks) != sorted(want_hooks):
        failures.append(f"hooks declared {want_hooks} != registered {sorted(ctx.hooks)}")
    print(f"registered: {len(ctx.tools)} tools, {len(ctx.hooks)} hook(s)")

    # pre_tool_call dispatch: mutating -> approve card; read-only -> None
    hook = ctx.hooks["pre_tool_call"][0]
    for name in ("smelt_run", "smelt_capture", "smelt_kill"):
        r = hook(name, {"target": "x.py:f", "job_id": "j1"})
        if not (isinstance(r, dict) and r.get("action") == "approve"
                and r.get("rule_key") == f"smelt:{name}" and r.get("message")):
            failures.append(f"{name}: expected approve card, got {r!r}")
    for name in ("smelt_scan", "smelt_job", "smelt_jobs", "smelt_report",
                 "smelt_apply", "smelt_verify", "smelt_doctor"):
        if hook(name, {}) is not None:
            failures.append(f"{name}: read-only verb must not prompt")
    if hook("some_other_tool", {}) is not None:
        failures.append("foreign tool must pass through untouched")
    print("pre_tool_call: mutating gated, read-only silent, foreign untouched")

    # drive a REAL handler through the registered tool surface
    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~/.cache")) as td:
        with open(os.path.join(td, "demo.py"), "w") as f:
            f.write("def shout(s: str) -> str:\n    return s.upper()\n")
        out = ctx.tools["smelt_scan"]["handler"]({"path": td})
        data = json.loads(out)
        if not data.get("ok"):
            # smelt CLI may be absent on this host — the handler must still
            # answer as structured data, never a traceback.
            if "error" not in data:
                failures.append(f"scan handler returned non-data: {out[:200]}")
            else:
                print(f"scan handler answered as data (CLI unavailable: {data['error'][:80]})")
        else:
            cands = data.get("candidates", [])
            if not any(c.get("function") == "shout" and c.get("status") == "candidate"
                       for c in cands):
                failures.append(f"scan did not find the demo candidate: {out[:300]}")
            else:
                print("scan handler: real CLI round-trip found the demo candidate")

    # bad input is data, not a traceback
    bad = json.loads(ctx.tools["smelt_run"]["handler"]({}))
    if bad.get("ok") or "error" not in bad:
        failures.append("run with no target must return a structured error")

    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("smoke_load: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
