#!/usr/bin/env python3
"""Generate the CLI reference HTML for the site.

Run:  python3 site/scripts/gen_cli_ref.py            # deterministic, uses the snapshot
      python3 site/scripts/gen_cli_ref.py --refresh  # re-capture `smelt --help` first

Output: site/_partials/cli-ref.html

The `smelt --help` text is read from site/_partials/smelt-help.txt, a committed
snapshot. CI must be able to regenerate this page byte-for-byte, and `uv run
smelt --help` is not reproducible on a bare runner (no uv, and building the
extension needs a Rust toolchain). Re-capture deliberately with --refresh after
the CLI changes, and commit the snapshot with the page.
"""
import argparse
import html
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SITE = REPO / "site"
SNAPSHOT = SITE / "_partials" / "smelt-help.txt"
OUT = SITE / "_partials" / "cli-ref.html"

EXIT_ROWS = [
    ("0", "accepted — verified, speedup clears the conservative 1.5x lower bound"),
    ("2", "config error (bad target, dotted qualname, unsupported annotation on a required path)"),
    ("3", "refused — impure target or unsupported-but-understood shape (typed, with a hint)"),
    ("4", "rejected — no acceptable rewrite within budget (a correct, honest outcome)"),
    ("5", "harness/internal error (report the run dir)"),
]


def refresh_snapshot() -> None:
    """Re-capture `smelt --help` into the committed snapshot."""
    try:
        out = subprocess.run(
            ["uv", "run", "smelt", "--help"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=180,
        )
        text = out.stdout or out.stderr
        if "Usage: smelt" not in text:
            raise RuntimeError(f"unexpected smelt --help output: {text[:200]}")
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(text)
        print(f"snapshot refreshed: {SNAPSHOT}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - report and keep the old snapshot
        print(f"WARN: could not refresh smelt --help ({exc}); keeping the snapshot", file=sys.stderr)


def load_help() -> str:
    if SNAPSHOT.exists():
        return SNAPSHOT.read_text()
    return "(site/_partials/smelt-help.txt is missing — run: gen_cli_ref.py --refresh)"


def cli_md() -> str:
    path = REPO / "docs" / "cli.md"
    return path.read_text() if path.exists() else ""


def usage_block() -> str:
    """The command/flag summary from docs/cli.md (its first fenced block)."""
    md = cli_md()
    if "```" not in md:
        return "see docs/cli.md"
    return md.split("```")[1]


def render() -> str:
    parts = [
        '<h2 id="cli-reference">CLI reference</h2>',
        '<p class="text-dim">Commands, flags and exit codes. The help text is a captured '
        'snapshot of <code>smelt --help</code>; regenerate it with '
        '<code>python3 site/scripts/gen_cli_ref.py --refresh</code>.</p>',
        "<h3>Commands</h3>",
        '<pre class="terminal-body"><code>' + html.escape(usage_block()) + "</code></pre>",
        "<h3>Exit codes</h3>",
        '<div class="table-wrap"><table><thead><tr><th>code</th><th>meaning</th></tr></thead><tbody>',
    ]
    for code, meaning in EXIT_ROWS:
        parts.append(f'<tr><td class="mono">{code}</td><td>{html.escape(meaning)}</td></tr>')
    parts.append("</tbody></table></div>")
    parts.append("<h3>Live <code>smelt --help</code></h3>")
    parts.append('<pre class="terminal-body"><code>' + html.escape(load_help()) + "</code></pre>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true", help="re-capture smelt --help first")
    args = ap.parse_args()

    if args.refresh:
        refresh_snapshot()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render())
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()