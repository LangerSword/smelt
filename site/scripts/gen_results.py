#!/usr/bin/env python3
"""Generate the results table HTML from evals/results.json.

Run:  python3 site/scripts/gen_results.py
The output is site/_partials/results.html (or stdout with --stdout).
Every number is labeled with the model that produced it.
"""
import json
import sys
import html
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
RESULTS_JSON = REPO / "evals" / "results.json"
OUT = Path(__file__).resolve().parent.parent / "_partials" / "results.html"


def fmt_x(v):
    return f"{v:.2f}x"


def render(results_json: Path, out_path: Path | None) -> str:
    data = json.loads(results_json.read_text())
    summary = data["summary"]
    rows = data["results"]

    model = summary["model"]
    provider = summary["provider"]

    parts = []
    parts.append(f'<p class="text-dim mono-label">Source: evals/results.json · provider <code>{html.escape(provider)}</code> · model <code>{html.escape(model)}</code> · ran on: laptop</p>')

    parts.append('<div class="results-strip">')
    parts.append(f'<div class="results-stat"><span class="num" data-count="{summary["tasks"]}">{summary["tasks"]}</span><span class="lbl">tasks</span></div>')
    parts.append(f'<div class="results-stat"><span class="num ingot" data-count="{summary["accepted"]}">{summary["accepted"]}</span><span class="lbl">accepted</span></div>')
    parts.append(f'<div class="results-stat"><span class="num slag" data-count="{summary["rejected"]}">{summary["rejected"]}</span><span class="lbl">rejected</span></div>')
    parts.append(f'<div class="results-stat"><span class="num ash" data-count="{summary["errors"]}">{summary["errors"]}</span><span class="lbl">errors</span></div>')
    parts.append('</div>')

    parts.append('<div class="table-wrap"><table class="results-table">')
    parts.append('<thead><tr><th>function</th><th>category</th><th>status</th><th>attempts</th><th>oracle cases</th><th>speedup</th><th>lower bound</th></tr></thead>')
    parts.append('<tbody>')
    for r in rows:
        status = r["status"]
        badge_cls = {"accepted": "ingot", "rejected": "slag"}.get(status, "ash")
        sp = fmt_x(r["speedup"]) if r.get("speedup") else "—"
        lb = fmt_x(r["speedup_lb"]) if r.get("speedup_lb") else "—"
        parts.append(
            f'<tr>'
            f'<td><code>{html.escape(r["function"])}</code></td>'
            f'<td>{html.escape(r["category"])}</td>'
            f'<td><span class="verdict-badge verdict-{badge_cls}">{status}</span></td>'
            f'<td>{r["attempts"]}</td>'
            f'<td>{r["oracle_cases"]}</td>'
            f'<td class="mono">{sp}</td>'
            f'<td class="mono text-dim">{lb}</td>'
            f'</tr>'
        )
    parts.append('</tbody></table></div>')

    parts.append("<h3>Speedups — measured, not modeled</h3>")
    parts.append('<p class="text-dim">The gold mark is the conservative lower bound — the acceptance rule reads it, not the median.</p>')
    max_sp = max((r["speedup"] for r in rows if r.get("speedup") and r["status"] == "accepted"), default=1)
    for r in sorted((r for r in rows if r.get("speedup") and r["status"] == "accepted"), key=lambda x: -x["speedup"]):
        w = (r["speedup"] / max_sp) * 100
        lb_w = (r["speedup_lb"] / max_sp) * 100
        parts.append(
            f'<div class="speedup-row">'
            f'<code>{html.escape(r["function"])}</code>'
            f'<div class="speedup-track">'
            f'<div class="speedup-bar-fill" data-w="{w:.1f}"></div>'
            f'<div class="speedup-lb" data-lb-w="{lb_w:.1f}" style="left:{lb_w:.1f}%"></div>'
            f'</div>'
            f'<span class="mono">{fmt_x(r["speedup"])}</span>'
            f'</div>'
        )

    out = "\n".join(parts)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out)
    return out


if __name__ == "__main__":
    stdout = "--stdout" in sys.argv
    html_out = render(RESULTS_JSON, None if stdout else OUT)
    if stdout:
        print(html_out)
    else:
        print(f"wrote {OUT}", file=sys.stderr)
