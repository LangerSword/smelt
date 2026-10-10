"""Honest run report: attempts (including failures), benchmark table, flags, outcome.

A rejected or refused run is a correct result and reads like one here. This file is
what the developer pastes into submissions — nothing is rounded up.
"""

import os


def write_report(run_dir: str, data: dict) -> str:
    L: list[str] = []
    L.append(f"# smelt run report — {data['run_id']}")
    L.append("")
    L.append(f"- target: `{data['target']['path']}:{data['target']['qualname']}` "
             f"(sha256 `{data['target']['source_sha256'][:12]}…`)")
    L.append(f"- provider: `{data['provider']['name']}` · model: `{data['provider'].get('model') or '—'}` · ran on: laptop")
    L.append(f"- oracle: {data['oracle'].get('n_cases', '?')} frozen cases, "
             f"hash `{(data['oracle'].get('sha256') or '')[:12]}…`")
    L.append("")
    L.append("## Attempts")
    L.append("")
    L.append("| # | source | build | verify | bench | outcome |")
    L.append("|---|--------|-------|--------|-------|---------|")
    for a in data.get("attempts", []):
        L.append(f"| {a.get('attempt')} | {a.get('source', '—')} | {a.get('build', '—')} "
                 f"| {a.get('verify', '—')} | {a.get('bench', '—')} | {a.get('outcome', '—')} |")
    if data.get("bench"):
        b = data["bench"]
        L.append("")
        L.append("## Benchmark (measured, not modeled)")
        L.append("")
        L.append(f"- python median {b['python_med_s'] * 1000:.2f} ms "
                 f"(CI {b['python_ci_lo_s'] * 1000:.2f}–{b['python_ci_hi_s'] * 1000:.2f} ms)")
        L.append(f"- rust   median {b['rust_med_s'] * 1000:.2f} ms "
                 f"(CI {b['rust_ci_lo_s'] * 1000:.2f}–{b['rust_ci_hi_s'] * 1000:.2f} ms)")
        L.append(f"- speedup: **{b['ratio']:.2f}x** (conservative lower bound {b['ratio_ci_lo']:.2f}x)")
        L.append(f"- workload: {b['workload_cases']} calls/rep · {b['reps']} reps "
                 f"(first {b['warmup']} discarded) · 4x-scaling ratio {b.get('ratio_scaled_4x', 0):.2f}x")
        L.append(f"- flags: {', '.join(b.get('flags') or ['none'])}")
    L.append("")
    L.append("## Outcome")
    L.append("")
    L.append(f"**{data['outcome']['status']}** — {data['outcome'].get('reason', '')}")
    L.append("")
    L.append("Honesty note: rejected and refused runs are correct results; nothing here is rounded up.")
    path = os.path.join(run_dir, "report.md")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    return path
