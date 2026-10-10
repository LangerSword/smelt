"""`smelt apply <run-dir>` — VIEW ONLY.

Prints the proposed change for an accepted run: the generated Rust module as a
new-file diff, the build command, and a safe try/except shim that falls back to
the original Python. It never writes into the target repo — applying the change
stays a manual, reviewed step.
"""

import json
import os
import sys


def _candidate_lib(run_dir: str) -> str | None:
    attempts_dir = os.path.join(run_dir, "attempts")
    if not os.path.isdir(attempts_dir):
        return None
    best = None
    for name in sorted(os.listdir(attempts_dir)):
        p = os.path.join(attempts_dir, name, "lib.rs")
        if os.path.exists(p):
            best = p  # keep the last (accepted) attempt
    return best


def apply(run_dir: str) -> int:
    state_path = os.path.join(run_dir, "state.json")
    try:
        with open(state_path) as f:
            st = json.load(f)
    except Exception as e:  # noqa: BLE001 — report, never crash
        print(f"smelt apply: cannot read {state_path}: {e}", file=sys.stderr)
        return 2

    status = st.get("status")
    if status != "accepted":
        print(f"smelt apply: run {st.get('run_id')} is {status!r} — nothing to apply "
              f"(only accepted runs carry a verified candidate)", file=sys.stderr)
        return 4

    cand = _candidate_lib(run_dir)
    if cand is None:
        print("smelt apply: candidate lib.rs not found in the run dir", file=sys.stderr)
        return 5

    tgt = st.get("target") or {}
    func = tgt.get("qualname") or "fn"
    attempts = st.get("attempts") or []
    bench = attempts[-1].get("bench", "") if attempts else ""

    lib = open(cand, encoding="utf-8").read()
    out = []
    out.append(f"# smelt apply — {st.get('run_id')} · VIEW ONLY (nothing is written)")
    out.append(f"# target : {tgt.get('path')}:{func}")
    out.append(f"# status : accepted · {bench}")
    out.append("")
    out.append("--- /dev/null")
    out.append(f"+++ rust/{func}/src/lib.rs")
    for ln in lib.splitlines():
        out.append("+" + ln)
    out.append("")
    out.append("## build (manual, in a scratch dir)")
    out.append(f"#   cd rust/{func} && maturin develop --release")
    out.append("")
    out.append("## safe shim — fall back to the original if the extension is unavailable")
    out.append("```python")
    out.append("try:")
    out.append(f"    from rust.{func} import {func} as _fast  # built by smelt, oracle-verified")
    out.append(f"    {func} = _fast")
    out.append("except Exception:  # extension missing — keep the Python original")
    out.append("    pass")
    out.append("```")
    print("\n".join(out))
    return 0
