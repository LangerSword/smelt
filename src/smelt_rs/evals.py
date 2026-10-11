"""Eval runner: run the frozen corpus sequentially, count provider calls, write results.

Rate-limit discipline: tasks run strictly sequentially, the provider poster retries
with backoff, a pause sits between tasks, and a global provider-call cap stops the run
early (remaining tasks are recorded as skipped — never silently dropped).

Outputs (both generated, never hand-edited):
  evals/results.json  — machine-readable, one record per task
  evals/results.md    — the table that goes into the README, including failures
"""

import glob
import json
import os
import time

from smelt_rs.providers import providers as prov
from smelt_rs.core import orchestrator

RESULTS_JSON = "evals/results.json"
RESULTS_MD = "evals/results.md"


def _write_md(results: list, summary: dict, path: str = RESULTS_MD) -> None:
    lines = [
        "# smelt eval results (generated — never hand-edited)",
        "",
        f"- provider `{summary['provider']}` · model `{summary['model'] or '—'}` · ran on laptop",
        f"- tasks {summary['tasks']} · completed {summary['completed']} · "
        f"accepted {summary['accepted']} · rejected {summary['rejected']} · other {summary['errors']}",
        f"- provider calls: {summary['provider_calls']} (cap {summary['max_calls']})",
        "",
        "| function | cat | status | attempts | oracle | speedup | lb | notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        sp = "%0.2fx" % r["speedup"] if r.get("speedup") else "—"
        lb = "%0.2fx" % r["speedup_lb"] if r.get("speedup_lb") else "—"
        note = (r.get("reason") or "").replace("|", "/")[:90]
        lines.append("| `%s` | %s | %s | %s | %s | %s | %s | %s |" % (
            r.get("function"), r.get("category"), r.get("status"), r.get("attempts", "—"),
            r.get("oracle_cases", "—"), sp, lb, note))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def run_corpus(*, corpus_dir: str = "evals/corpus", runs_dir: str = "evals/runs",
               provider: str = "gemini", model: str | None = None, max_calls: int = 120,
               pause_s: float = 3.0, max_attempts: int = 3, cases: int = 200,
               quiet: bool = False, out_tag: str = "") -> tuple[int, dict]:
    tasks = sorted(glob.glob(os.path.join(corpus_dir, "**", "*.py"), recursive=True))
    prov.CALLS.update({"attempts": 0, "ok": 0, "by_model": {}})
    results = []
    for path in tasks:
        stem = os.path.splitext(os.path.basename(path))[0]
        cat = os.path.basename(os.path.dirname(path))
        if prov.CALLS["attempts"] >= max_calls:
            results.append({"function": stem, "category": cat, "status": "skipped",
                            "reason": f"global provider-call cap reached ({max_calls})"})
            continue
        t0 = time.time()
        code, info = orchestrator.run(
            target=os.path.abspath(path) + ":" + stem, provider_name=provider, model=model,
            runs_dir=os.path.join(runs_dir, stem), max_attempts=max_attempts,
            target_cases=cases, quiet=True)
        bench = info.get("bench") or {}
        results.append({
            "function": stem, "category": cat, "exit_code": code,
            "status": info.get("status"), "attempts": len(info.get("attempts") or []),
            "oracle_cases": (info.get("oracle") or {}).get("n_cases"),
            "speedup": bench.get("ratio"), "speedup_lb": bench.get("ratio_ci_lo"),
            "flags": bench.get("flags"), "reason": (info.get("stop_reason") or "")[:200],
            "wall_s": round(time.time() - t0, 1),
        })
        if not quiet:
            sp = "x%0.2f" % bench["ratio"] if bench.get("ratio") else "—"
            print("[evals] %-18s %-9s %7s (%ss)" % (stem, results[-1]["status"], sp,
                                                    results[-1]["wall_s"]), flush=True)
        time.sleep(pause_s)

    summary = {
        "provider": provider, "model": model, "tasks": len(tasks),
        "completed": sum(1 for r in results if r.get("status") != "skipped"),
        "accepted": sum(1 for r in results if r.get("status") == "accepted"),
        "rejected": sum(1 for r in results if r.get("status") == "rejected"),
        "errors": sum(1 for r in results if r.get("status") not in ("accepted", "rejected", "skipped")),
        "provider_calls": json.loads(json.dumps(prov.CALLS)),
        "max_calls": max_calls,
    }
    os.makedirs("evals", exist_ok=True)
    rj = "evals/results%s.json" % out_tag
    rm = "evals/results%s.md" % out_tag
    with open(rj, "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)
    _write_md(results, summary, rm)
    if not quiet:
        print(json.dumps(summary, indent=2))
    return 0, {"summary": summary, "results": results}
