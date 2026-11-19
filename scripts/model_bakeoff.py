#!/usr/bin/env python
"""Model bake-off (v0.8): pick the nvidia default model EMPIRICALLY.

Runs a fixed mini-corpus (one str / one int / one list task) against each
candidate model with the shipping pipeline (repair on, same gates). Selection
rule, in order: most accepted tasks -> fewest provider calls -> highest median
speedup lower bound. Every number is labeled with its model; nothing is
hand-edited. A per-task wall-clock cap (TASK_TIMEOUT_S, equal for all models)
bounds NIM stalls on long-reasoning prompts; capped tasks are recorded as
`timeout`, never silently dropped. Output: evals/bakeoff-v08.json (+ stdout).

Usage: uv run python scripts/model_bakeoff.py [--max-calls 40]
"""

import argparse
import json
import os
import signal
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from smelt_rs.core import orchestrator  # noqa: E402
from smelt_rs.providers import providers as prov  # noqa: E402

# Per-task wall-clock cap. Observed legitimate tasks finish in 100-175 s;
# NVIDIA NIM sometimes STALLS on long-reasoning prompts (no 429, no response,
# socket held open) — without a cap one task burned 24 min of retry envelope.
# The cap applies equally to every model and is recorded honestly as timeout.
TASK_TIMEOUT_S = 420


class TaskTimeout(BaseException):
    """BaseException on purpose: orchestrator.run's `except Exception` must NOT
    swallow the cap — it propagates to the bake-off's own handler."""


def _alarm(signum, frame):
    raise TaskTimeout()


signal.signal(signal.SIGALRM, _alarm)

TASKS = [
    "evals/corpus/string/caesar_shift.py:caesar_shift",
    "evals/corpus/int/collatz_steps.py:collatz_steps",
    "evals/corpus/list/max_subarray.py:max_subarray",
]
MODELS = [
    # Lineup adjusted 2026-11-19 during the run: the big reasoning endpoints
    # (mistral-large, kimi-k3.1-pro, glm-5.3-flash) began STALLING on codegen
    # prompts (short probes fine, long generations hang past the retry
    # envelope). Pre-probes with the real rle_encode prompt picked the
    # responsive models below; mistral-large stays in for a fair retry —
    # stalls record as timeout, never silently dropped.
    "mistralai/mistral-large-4-1t-a52b",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "minimaxai/minimax-m3.1-flash",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-calls", type=int, default=40, help="global provider-call cap")
    ap.add_argument("--models", nargs="*", default=MODELS)
    args = ap.parse_args()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runs_root = os.path.join(repo, "evals", "runs-bakeoff")
    os.makedirs(runs_root, exist_ok=True)
    prov.CALLS.update({"attempts": 0, "ok": 0, "by_model": {}})
    results = []
    for model in args.models:
        for target in TASKS:
            if prov.CALLS["attempts"] >= args.max_calls:
                results.append({"model": model, "target": target, "status": "skipped",
                                "reason": "global call cap reached"})
                continue
            stem = target.split(":")[1]
            t0 = time.time()
            signal.alarm(TASK_TIMEOUT_S)
            try:
                code, info = orchestrator.run(
                    target=os.path.join(repo, target), provider_name="nvidia", model=model,
                    runs_dir=os.path.join(runs_root, f"{model.replace('/', '_')}__{stem}"),
                    max_attempts=3, target_cases=200, quiet=True)
            except TaskTimeout:
                code, info = -1, {"status": "timeout",
                                  "stop_reason": f"task wall-clock cap ({TASK_TIMEOUT_S}s) — "
                                                 "provider call did not return (NIM stall)",
                                  "attempts": [], "bench": {}}
            finally:
                signal.alarm(0)
            bench = info.get("bench") or {}
            rec = {"model": model, "target": target, "exit_code": code,
                   "status": info.get("status"),
                   "attempts": len(info.get("attempts") or []),
                   "speedup": bench.get("ratio"), "speedup_lb": bench.get("ratio_ci_lo"),
                   "reason": (info.get("stop_reason") or "")[:160],
                   "wall_s": round(time.time() - t0, 1)}
            results.append(rec)
            print(f"{model:45s} {stem:16s} {rec['status']:10s} "
                  f"lb={rec['speedup_lb'] or 0:.2f} attempts={rec['attempts']} "
                  f"({rec['wall_s']}s)", flush=True)
            time.sleep(2)
    per_model = {}
    for m in args.models:
        rs = [r for r in results if r["model"] == m and r.get("status") != "skipped"]
        acc = [r for r in rs if r.get("status") == "accepted"]
        lbs = [r["speedup_lb"] for r in acc if r.get("speedup_lb")]
        per_model[m] = {"tasks": len(rs), "accepted": len(acc),
                        "median_lb": statistics.median(lbs) if lbs else 0.0,
                        "calls": prov.CALLS["by_model"].get(m, 0)}
    ranked = sorted(per_model.items(),
                    key=lambda kv: (-kv[1]["accepted"], kv[1]["calls"], -kv[1]["median_lb"]))
    summary = {"tasks": TASKS, "max_calls": args.max_calls,
               "task_timeout_s": TASK_TIMEOUT_S,
               "provider_calls": json.loads(json.dumps(prov.CALLS)),
               "per_model": per_model,
               "ranking": [m for m, _ in ranked],
               "selected_default": ranked[0][0] if ranked else None}
    out = os.path.join(repo, "evals", "bakeoff-v08.json")
    with open(out, "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)
    print(json.dumps(summary, indent=2))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
