#!/usr/bin/env python
"""Blind generalization run: the FROZEN list, no tuning (v0.8 re-run tool).

Anti-cherry-pick proof: evals/general_frozen_list.json is read verbatim and its
sha256 recorded; functions are never swapped. Repo commit SHAs are recorded at
run time (upstream may have moved since the original freeze — noted honestly).
The original protocol (Oct 2026) used gemini/gemma-4-26b-a4b-it; v0.8 re-runs
use the upgraded pipeline and whatever provider/model is passed — the protocol
delta is written into the report, never hidden.

Usage:
  uv run python scripts/blind_run.py --repos-root <dir> [--provider nvidia]
      [--model M] [--max-calls 50] [--out-tag -v08]
Outputs: evals/general<tag>.json + evals/general<tag>.md (generated).
"""

import argparse
import hashlib
import json
import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from smelt_rs.core import orchestrator  # noqa: E402
from smelt_rs.providers import providers as prov  # noqa: E402

# Per-task wall-clock cap (equal for all targets): NIM can stall on
# long-reasoning prompts; capped tasks record as timeout, never dropped.
TASK_TIMEOUT_S = 420


class _TaskTimeout(BaseException):
    pass


def _alarm(signum, frame):
    raise _TaskTimeout()


signal.signal(signal.SIGALRM, _alarm)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos-root", required=True)
    ap.add_argument("--provider", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-attempts", type=int, default=2)
    ap.add_argument("--max-calls", type=int, default=50)
    ap.add_argument("--cases", type=int, default=200)
    ap.add_argument("--out-tag", default="-v08")
    args = ap.parse_args()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frozen_path = os.path.join(repo, "evals", "general_frozen_list.json")
    frozen_bytes = open(frozen_path, "rb").read()
    frozen = json.loads(frozen_bytes)
    freeze_sha = hashlib.sha256(frozen_bytes).hexdigest()
    provider = args.provider or prov.resolve_default_provider()
    model = prov.resolve_model(provider, args.model)

    shas = {}
    for name in frozen["repos"]:
        d = os.path.join(args.repos_root, name)
        try:
            import subprocess
            shas[name] = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"],
                                        capture_output=True, text=True, timeout=15).stdout.strip()
        except Exception:
            shas[name] = "unknown"

    prov.CALLS.update({"attempts": 0, "ok": 0, "by_model": {}})
    results = []
    for f in frozen["functions"]:
        target = os.path.join(args.repos_root, f["repo"], f["file"]) + ":" + f["fn"]
        if prov.CALLS["attempts"] >= args.max_calls:
            results.append({**f, "status": "skipped", "reason": "global call cap reached"})
            continue
        t0 = time.time()
        signal.alarm(TASK_TIMEOUT_S)
        try:
            code, info = orchestrator.run(target=target, provider_name=provider, model=model,
                                          runs_dir=os.path.join(repo, "evals", "runs-blind" + args.out_tag,
                                                                f"{f['repo']}__{f['fn'].replace('.', '_')}"),
                                          max_attempts=args.max_attempts, target_cases=args.cases,
                                          quiet=True)
        except _TaskTimeout:
            code, info = -1, {"status": "timeout",
                              "stop_reason": f"task wall-clock cap ({TASK_TIMEOUT_S}s) — "
                                             "provider call did not return",
                              "attempts": [], "bench": {}}
        finally:
            signal.alarm(0)
        bench = info.get("bench") or {}
        rec = {**f, "exit_code": code, "status": info.get("status"),
               "reason": (info.get("stop_reason") or info.get("reason") or "")[:220],
               "attempts": len(info.get("attempts") or []),
               "speedup": bench.get("ratio"), "speedup_lb": bench.get("ratio_ci_lo"),
               "wall_s": round(time.time() - t0, 1)}
        results.append(rec)
        print(f"{f['n']:2d} {f['repo']:10s} {f['fn']:20s} {rec['status']:12s} "
              f"{rec['reason'][:80]}", flush=True)

    summary = {"provider": provider, "model": model, "freeze_sha256": freeze_sha,
               "repo_shas": shas, "max_attempts": args.max_attempts,
               "max_calls": args.max_calls,
               "accepted": sum(1 for r in results if r.get("status") == "accepted"),
               "rejected": sum(1 for r in results if r.get("status") == "rejected"),
               "refused": sum(1 for r in results if r.get("status") == "refused"),
               "config_error": sum(1 for r in results if r.get("status") == "config_error"),
               "errors": sum(1 for r in results if r.get("status") not in
                             ("accepted", "rejected", "refused", "config_error", "skipped")),
               "provider_calls": json.loads(json.dumps(prov.CALLS))}
    os.makedirs(os.path.join(repo, "evals"), exist_ok=True)
    jpath = os.path.join(repo, "evals", f"general{args.out_tag}.json")
    with open(jpath, "w") as fh:
        json.dump({"summary": summary, "results": results}, fh, indent=2)
    L = ["# smelt — blind generalization re-run (generated — never hand-edited)", "",
         f"Same frozen list (`evals/general_frozen_list.json`, sha256 `{freeze_sha[:16]}…` — "
         "functions never swapped). Pipeline: v0.8 (repair loop, package loading, domain guard).",
         f"Provider `{provider}` · model `{model}` · max-attempts {args.max_attempts} · "
         f"call cap {args.max_calls}. Protocol delta vs the Oct-2026 run: provider/model "
         "(then gemini/gemma-4-26b-a4b-it) and the upgraded pipeline; the list is identical.",
         "", "Repo commits at run time: " + " · ".join(f"{k} `{v[:12]}`" for k, v in shas.items()),
         "", "| # | repo | function | expected | outcome | reason | speedup (lb) | attempts |",
         "|---|---|---|---|---|---|---|---|"]
    for r in results:
        sp = f"{r['speedup']:.2f}x ({r['speedup_lb']:.2f}x)" if r.get("speedup") else "—"
        L.append(f"| {r['n']} | {r['repo']} | `{r['file']}:{r['fn']}` | {r['expect']} "
                 f"| {r.get('status')} | {(r.get('reason') or '').replace('|', '/')[:120]} "
                 f"| {sp} | {r.get('attempts', '—')} |")
    L += ["", f"**Totals:** accepted {summary['accepted']} · rejected {summary['rejected']} · "
          f"refused {summary['refused']} · config errors {summary['config_error']} · "
          f"other errors {summary['errors']} · provider calls {summary['provider_calls']['attempts']} "
          f"(cap {args.max_calls}).", ""]
    mpath = os.path.join(repo, "evals", f"general{args.out_tag}.md")
    with open(mpath, "w") as fh:
        fh.write("\n".join(L))
    print(json.dumps(summary, indent=2))
    print("wrote", jpath, "and", mpath)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
