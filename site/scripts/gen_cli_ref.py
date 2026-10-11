#!/usr/bin/env python3
"""Generate the CLI reference HTML from `smelt --help` and docs/cli.md.

Run:  python3 site/scripts/gen_cli_ref.py
Output: site/_partials/cli-ref.html
"""
import subprocess
import sys
import html
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
OUT = Path(__file__).resolve().parent.parent / "_partials" / "cli-ref.html"


def run_smelt_help() -> str:
    try:
        out = subprocess.run(
            ["uv", "run", "smelt", "--help"],
            cwd=REPO, capture_output=True, text=True, timeout=120,
        )
        return out.stdout or out.stderr
    except Exception as e:
        return f"(smelt --help unavailable: {e})"


def cli_md() -> str:
    p = REPO / "docs" / "cli.md"
    return p.read_text() if p.exists() else ""


def render() -> str:
    parts = []
    parts.append('<h2 id="cli-reference">CLI reference</h2>')
    parts.append('<p class="text-dim">Generated from <code>smelt --help</code> and <code>docs/cli.md</code>. Every command, flag and exit code.</p>')

    parts.append("<h3>Commands</h3>")
    parts.append('<pre class="terminal-body"><code>' + html.escape(cli_md().split("```")[1] if "```" in cli_md() else "see docs/cli.md") + "</code></pre>")

    parts.append("<h3>Exit codes</h3>")
    parts.append('<div class="table-wrap"><table><thead><tr><th>code</th><th>meaning</th></tr></thead><tbody>')
    exit_rows = [
        ("0", "accepted — verified, speedup clears the conservative 1.5x lower bound"),
        ("2", "config error (bad target, dotted qualname, unsupported annotation on a required path)"),
        ("3", "refused — impure target or unsupported-but-understood shape (typed, with a hint)"),
        ("4", "rejected — no acceptable rewrite within budget (a correct, honest outcome)"),
        ("5", "harness/internal error (report the run dir)"),
    ]
    for c, m in exit_rows:
        parts.append(f'<tr><td class="mono">{c}</td><td>{html.escape(m)}</td></tr>')
    parts.append("</tbody></table></div>")

    parts.append("<h3>Live <code>smelt --help</code></h3>")
    parts.append('<pre class="terminal-body"><code>' + html.escape(run_smelt_help()) + "</code></pre>")

    return "\n".join(parts)


if __name__ == "__main__":
    out = render()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out)
    print(f"wrote {OUT}", file=sys.stderr)
