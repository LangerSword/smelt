"""Approval gate: mutating smelt verbs ask the user first (fail closed).

Read-only verbs (scan/doctor/job/jobs/verify/report/apply) pass without a
prompt — apply is view-only by design. run/capture/kill change state or spend
model calls, so they carry an approval card naming the exact target/job.
"""

from __future__ import annotations

try:
    from . import smelt_agent_api as A
except ImportError:
    import smelt_agent_api as A


def pre_tool_call(tool_name: str, args: dict | None = None, **_kwargs):
    if tool_name not in A.MUTATING:
        return None
    args = args or {}
    if tool_name == "smelt_run":
        detail = f"target={args.get('target', '?')} provider={args.get('provider') or '(auto)'}"
        if args.get("model"):
            detail += f" model={args['model']}"
        msg = f"smelt run (detached job, spends model calls): {detail}"
    elif tool_name == "smelt_capture":
        msg = f"smelt capture (runs the target function, writes an oracle): {args.get('target', '?')}"
    else:  # smelt_kill
        msg = f"smelt kill (stops a running job's process group): job={args.get('job_id', '?')}"
    return {"action": "approve", "message": msg, "rule_key": f"smelt:{tool_name}"}
