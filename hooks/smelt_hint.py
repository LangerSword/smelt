#!/usr/bin/env python3
"""PostToolUse hint: after a Python file edit, surface smelt-able candidates.

Reads the Claude Code hook payload on stdin; when the edited file is a .py
module, runs `smelt scan <dir> --json` (bounded, silent on any failure) and —
only if THAT file has tier-1 candidates — emits additionalContext suggesting
the verified-Rust path. Never blocks or breaks the edit: every error path
exits 0 with no output. No secrets are read; scan is static AST analysis.
"""

import json
import os
import shutil
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path") or ""
    if not path.endswith(".py") or not os.path.isfile(path):
        return 0
    smelt = os.environ.get("SMELT_BIN") or shutil.which("smelt")
    if not smelt:
        return 0
    try:
        p = subprocess.run([smelt, "scan", os.path.dirname(os.path.abspath(path)), "--json"],
                           capture_output=True, text=True, timeout=10)
        if p.returncode != 0:
            return 0
        data = json.loads(p.stdout)
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        return 0
    rel = os.path.basename(path)
    hits = [c for c in data.get("candidates", [])
            if c.get("status") == "candidate" and c.get("file") == rel]
    if not hits:
        return 0
    lines = [f"- {rel}:{c['function']} ({c.get('reason', '')})" for c in hits[:5]]
    ctx = ("smelt: this file has verified-Rust candidates (pure, supported types):\n"
           + "\n".join(lines)
           + "\nIf a hot path here needs speed, offer /smelt-run <file:function> — "
             "oracle-gated, measured speedup, honest rejection. Do not run it unprompted.")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": ctx}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
