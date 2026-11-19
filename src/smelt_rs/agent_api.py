"""Agent API: one stdlib-only handler core for every agent surface.

The MCP server (`smelt mcp`), the Hermes plugin and the Claude Code plugin all
wrap THESE handlers — never a second implementation. Every handler takes a
dict and returns a JSON-serializable dict; errors are data ({"ok": False,
"error": ...}), never exceptions across the surface boundary.

The core drives the installed `smelt` CLI (resolved SMELT_BIN -> PATH ->
`uv run smelt` in a checkout) because the CLI is smelt's stable public
surface. Long runs are DETACHED JOBS (the agent call returns immediately;
the child survives it): job dir with meta.json, log.txt and a child-written
exit_code file; poll/tail/kill/verify are separate verbs.

Child environments are an allowlist plus EXACTLY the provider-key names
smelt's provider layer resolves — never the whole host environment (the
agent's other secrets must not leak into a job log). Dropped secret-like
names are recorded (names only, never values).
"""

import json
import os
import shlex
import shutil
import signal
import subprocess
import time

JOBS_SCHEMA = 1
DEFAULT_RUNS_DIR = "runs"

# The ONLY secret names forwarded to a job child: exactly what
# smelt_rs.providers.providers.resolve_secret may look up.
PROVIDER_KEY_NAMES = (
    "NVIDIA_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "DIGITALOCEAN_TOKEN",
    "SMELT_OPENAI_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "SMELT_PROVIDER_KEY",
)
ENV_ALLOWLIST = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "TERM", "TMPDIR", "TZ",
                 "XDG_RUNTIME_DIR", "DISPLAY", "WAYLAND_DISPLAY")
SECRET_NAME_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")


class AgentApiError(Exception):
    """Bad input — returned as structured error data by the wrappers."""


def _err(msg: str, **extra) -> dict:
    return {"ok": False, "error": msg, **extra}


def jobs_root() -> str:
    d = os.environ.get("SMELT_JOBS_DIR") or os.path.expanduser("~/.cache/smelt/jobs")
    os.makedirs(d, exist_ok=True)
    return d


def smelt_argv() -> list[str]:
    """Resolve the smelt CLI: SMELT_BIN -> PATH -> uv run smelt (checkout)."""
    env_bin = os.environ.get("SMELT_BIN")
    if env_bin:
        return shlex.split(env_bin)
    found = shutil.which("smelt")
    if found:
        return [found]
    if shutil.which("uv"):
        return ["uv", "run", "smelt"]
    raise AgentApiError("smelt CLI not found — install smelt-rs, set SMELT_BIN, "
                        "or run from a checkout with uv")


def child_environment(extra: dict | None = None) -> tuple[dict, list[str]]:
    """Allowlist env + the exact provider keys smelt resolves. Returns (env,
    dropped_secret_names) — names only, values are never recorded."""
    env = {}
    for k in ENV_ALLOWLIST:
        if k in os.environ:
            env[k] = os.environ[k]
    for k in os.environ:
        if k.startswith("LC_"):
            env[k] = os.environ[k]
    for k in os.environ:
        if k.startswith("SMELT_") and k not in PROVIDER_KEY_NAMES:
            env[k] = os.environ[k]  # SMELT_* config knobs (bases, models, retries)
    for k in PROVIDER_KEY_NAMES:
        if k in os.environ:
            env[k] = os.environ[k]
    dropped = sorted(k for k in os.environ
                     if k not in env and any(m in k.upper() for m in SECRET_NAME_MARKERS))
    if extra:
        env.update(extra)
    return env, dropped


def _cli_json(args: list[str], timeout: int = 120, cwd: str | None = None) -> dict:
    """Run a smelt CLI command with --json and parse its summary."""
    argv = smelt_argv() + args
    env, _ = child_environment()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           cwd=cwd, env=env)
    except subprocess.TimeoutExpired:
        return _err(f"smelt {' '.join(args[:2])} timed out after {timeout}s")
    except FileNotFoundError as e:
        return _err(f"cannot launch smelt: {e}")
    out = (p.stdout or "").strip()
    data: dict
    try:
        # scan/doctor print indented multi-line JSON; run prints one line.
        data = json.loads(out) if out else {}
    except json.JSONDecodeError:
        try:
            data = json.loads(out.splitlines()[-1]) if out else {}
        except (json.JSONDecodeError, IndexError):
            data = {"raw": out[:2000]}
    if not isinstance(data, dict):
        data = {"raw": out[:2000]}
    if isinstance(data, dict):
        data.setdefault("exit_code", p.returncode)
        if p.returncode != 0 and "error" not in data and "status" not in data:
            data["error"] = (p.stderr or out)[:500] or f"exit {p.returncode}"
        data["ok"] = p.returncode == 0
    return data


# ------------------------------------------------------------------ read-only verbs

def h_scan(args: dict) -> dict:
    path = args.get("path")
    if not path or not isinstance(path, str):
        return _err("scan needs 'path' (directory to scan)")
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return _err(f"not a directory: {path}")
    return _cli_json(["scan", path, "--json"])


def h_doctor(args: dict) -> dict:
    argv = ["doctor", "--json"]
    if args.get("probe"):
        argv.append("--probe")
    return _cli_json(argv, timeout=180)


def h_report(args: dict) -> dict:
    run_dir = args.get("run_dir")
    if not run_dir:
        return _err("report needs 'run_dir'")
    run_dir = os.path.abspath(os.path.expanduser(run_dir))
    path = os.path.join(run_dir, "report.md")
    if not os.path.isfile(path):
        return _err(f"no report at {path}")
    with open(path) as f:
        return {"ok": True, "run_dir": run_dir, "report": f.read()}


def h_apply(args: dict) -> dict:
    run_dir = args.get("run_dir")
    if not run_dir:
        return _err("apply needs 'run_dir'")
    run_dir = os.path.abspath(os.path.expanduser(run_dir))
    argv = smelt_argv() + ["apply", run_dir]
    env, _ = child_environment()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=60, env=env)
    except subprocess.TimeoutExpired:
        return _err("smelt apply timed out")
    return {"ok": p.returncode == 0, "exit_code": p.returncode,
            "view_only": True, "diff": p.stdout, "error": p.stderr[:500] if p.returncode else ""}


def h_capture(args: dict) -> dict:
    target = args.get("target")
    if not target or ":" not in str(target):
        return _err("capture needs 'target' as path/to/file.py:function")
    argv = ["capture", str(target), "--json"]
    if args.get("cases"):
        argv += ["--cases", str(int(args["cases"]))]
    if args.get("seed") is not None:
        argv += ["--seed", str(int(args["seed"]))]
    if args.get("runs_dir"):
        argv += ["--runs-dir", str(args["runs_dir"])]
    return _cli_json(argv, timeout=300)


# ------------------------------------------------------------------ detached run jobs

def _atomic_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _job_dir(job_id: str) -> str:
    if not job_id or "/" in job_id or ".." in job_id:
        raise AgentApiError(f"invalid job_id: {job_id!r}")
    return os.path.join(jobs_root(), job_id)


def h_run(args: dict) -> dict:
    """Start a smelt run as a DETACHED job; returns immediately with a job id."""
    target = args.get("target")
    if not target or ":" not in str(target):
        return _err("run needs 'target' as path/to/file.py:function")
    target = str(target)
    runs_dir = os.path.abspath(os.path.expanduser(args.get("runs_dir") or DEFAULT_RUNS_DIR))
    os.makedirs(runs_dir, exist_ok=True)
    job_id = time.strftime("%y%m%d-%H%M%S") + "-" + os.urandom(3).hex()
    jd = _job_dir(job_id)
    os.makedirs(jd, exist_ok=True)

    argv = smelt_argv() + ["run", target, "--json", "--runs-dir", runs_dir]
    if args.get("provider"):
        argv += ["--provider", str(args["provider"])]
    if args.get("model"):
        argv += ["--model", str(args["model"])]
    if args.get("max_attempts"):
        argv += ["--max-attempts", str(int(args["max_attempts"]))]
    if args.get("cases"):
        argv += ["--cases", str(int(args["cases"]))]
    if args.get("seed") is not None:
        argv += ["--seed", str(int(args["seed"]))]
    if args.get("repair") is False:
        argv.append("--no-repair")
    if args.get("candidate"):
        argv += ["--candidate", str(args["candidate"])]

    env, dropped = child_environment()
    log_path = os.path.join(jd, "log.txt")
    # The CHILD writes its own exit code — a wrapper crash stays visible.
    cmd = shlex.join(argv) + f" > {shlex.quote(log_path)} 2>&1; echo $? > {shlex.quote(os.path.join(jd, 'exit_code'))}"
    try:
        p = subprocess.Popen(["sh", "-c", cmd], cwd=os.getcwd(), env=env,
                             start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError as e:
        return _err(f"cannot launch smelt job: {e}")
    meta = {"schema": JOBS_SCHEMA, "job_id": job_id, "target": target,
            "provider": args.get("provider") or "(auto)", "model": args.get("model") or "(default)",
            "started": time.time(), "pid": p.pid, "runs_dir": runs_dir,
            "cmd": argv, "dropped_secret_names": dropped}
    _atomic_json(os.path.join(jd, "meta.json"), meta)
    return {"ok": True, "job_id": job_id, "job_dir": jd, "pid": p.pid,
            "poll": "smelt_job", "note": "detached — the run survives this call; "
                                         "poll with smelt_job, stop with smelt_kill"}


def _read_meta(jd: str) -> dict | None:
    try:
        with open(os.path.join(jd, "meta.json")) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def _find_run_dir(meta: dict) -> str | None:
    """The run dir this job wrote: parse --json output from the log, else the
    newest dir under runs_dir created after the job started."""
    log_path = os.path.join(meta["job_dir"], "log.txt")
    try:
        with open(log_path) as f:
            for line in reversed(f.read().splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        d = json.loads(line)
                        if d.get("run_dir"):
                            return d["run_dir"]
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    try:
        cands = [os.path.join(meta["runs_dir"], n) for n in os.listdir(meta["runs_dir"])]
        cands = [d for d in cands if os.path.isdir(d) and os.path.getmtime(d) >= meta["started"] - 2]
        return max(cands, key=os.path.getmtime) if cands else None
    except OSError:
        return None


def _job_status(meta: dict) -> dict:
    jd = meta["job_dir"]
    exit_code = None
    try:
        exit_code = int(open(os.path.join(jd, "exit_code")).read().strip())
    except (OSError, ValueError):
        pass
    alive = _pid_alive(meta["pid"])
    run_dir = _find_run_dir(meta)
    run_state = None
    if run_dir:
        try:
            with open(os.path.join(run_dir, "state.json")) as f:
                st = json.load(f)
            run_state = {"status": st.get("status"), "stop_reason": st.get("stop_reason"),
                         "attempts": len(st.get("attempts") or []),
                         "oracle_cases": (st.get("oracle") or {}).get("n_cases")}
        except (OSError, json.JSONDecodeError):
            pass
    if exit_code is not None:
        state = "done"
    elif alive:
        state = "running"
    else:
        state = "lost"  # pid gone, no exit code — wrapper crashed
    return {"job_id": meta["job_id"], "state": state, "exit_code": exit_code,
            "target": meta["target"], "provider": meta.get("provider"),
            "model": meta.get("model"), "started": meta["started"],
            "elapsed_s": round(time.time() - meta["started"], 1),
            "run_dir": run_dir, "run": run_state}


def h_job(args: dict) -> dict:
    try:
        jd = _job_dir(args.get("job_id", ""))
    except AgentApiError as e:
        return _err(str(e))
    meta = _read_meta(jd)
    if meta is None:
        return _err(f"unknown job: {args.get('job_id')!r}")
    meta["job_dir"] = jd
    out = {"ok": True, **_job_status(meta)}
    tail = int(args.get("tail") or 0)
    if tail > 0:
        try:
            with open(os.path.join(jd, "log.txt")) as f:
                out["log_tail"] = f.read().splitlines()[-tail:]
        except OSError:
            out["log_tail"] = []
    return out


def h_jobs(args: dict) -> dict:
    root = jobs_root()
    jobs = []
    for name in os.listdir(root):
        jd = os.path.join(root, name)
        meta = _read_meta(jd)
        if meta:
            meta["job_dir"] = jd
            jobs.append(_job_status(meta))
    jobs.sort(key=lambda j: j["started"], reverse=True)
    return {"ok": True, "jobs": jobs[: int(args.get("limit") or 20)]}


def h_kill(args: dict) -> dict:
    try:
        jd = _job_dir(args.get("job_id", ""))
    except AgentApiError as e:
        return _err(str(e))
    meta = _read_meta(jd)
    if meta is None:
        return _err(f"unknown job: {args.get('job_id')!r}")
    meta["job_dir"] = jd
    st = _job_status(meta)
    if st["state"] != "running":
        return {"ok": True, "job_id": meta["job_id"], "already": st["state"]}
    try:
        os.killpg(meta["pid"], signal.SIGTERM)  # whole group: cargo + workers too
    except (ProcessLookupError, PermissionError):
        pass
    for _ in range(20):
        if not _pid_alive(meta["pid"]):
            break
        time.sleep(0.25)
    if _pid_alive(meta["pid"]):
        try:
            os.killpg(meta["pid"], signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    return {"ok": True, "job_id": meta["job_id"], "killed": True,
            "note": "run dir kept — resume with smelt resume <run_dir>"}


def h_verify(args: dict) -> dict:
    """Verify means the ARTIFACTS are fresh and terminal, not just exit 0."""
    try:
        jd = _job_dir(args.get("job_id", ""))
    except AgentApiError as e:
        return _err(str(e))
    meta = _read_meta(jd)
    if meta is None:
        return _err(f"unknown job: {args.get('job_id')!r}")
    meta["job_dir"] = jd
    st = _job_status(meta)
    problems = []
    if st["state"] != "done":
        problems.append(f"job not finished (state={st['state']})")
    run_dir = st.get("run_dir")
    if not run_dir:
        problems.append("no run directory found for this job")
    else:
        for name in ("state.json", "report.md", "events.jsonl"):
            p = os.path.join(run_dir, name)
            if not os.path.isfile(p):
                problems.append(f"missing artifact: {name}")
            elif os.path.getmtime(p) < meta["started"] - 2:
                problems.append(f"stale artifact (older than the job): {name}")
        rs = st.get("run") or {}
        if rs.get("status") not in ("accepted", "rejected", "refused", "error", "config_error", "captured"):
            problems.append(f"run state not terminal: {rs.get('status')!r}")
    return {"ok": not problems, "job_id": meta["job_id"], "run_dir": run_dir,
            "run": st.get("run"), "problems": problems}


HANDLERS = {
    "smelt_scan": h_scan,
    "smelt_doctor": h_doctor,
    "smelt_capture": h_capture,
    "smelt_run": h_run,
    "smelt_job": h_job,
    "smelt_jobs": h_jobs,
    "smelt_kill": h_kill,
    "smelt_verify": h_verify,
    "smelt_report": h_report,
    "smelt_apply": h_apply,
}

# Mutating verbs — agent surfaces must gate these behind user approval.
MUTATING = {"smelt_run", "smelt_capture", "smelt_kill"}

TOOL_DESCRIPTIONS = {
    "smelt_scan": "List smelt-able candidate functions under a directory (pure, supported types) with skip reasons. Read-only.",
    "smelt_doctor": "Check the smelt toolchain, sandbox worker and provider keys. probe=true sends tiny live calls. Read-only.",
    "smelt_capture": "Freeze a differential oracle for path/to/file.py:function by RUNNING it (200+ cases, hashed, read-only). No model calls. Writes run artifacts.",
    "smelt_run": "Start a full smelt loop (oracle -> model writes Rust -> safety scan -> build -> verify every case -> bench) as a DETACHED job. Returns a job_id immediately; poll smelt_job. Acceptance is code-gated: verified + conservative speedup lower bound >= 1.5x.",
    "smelt_job": "Poll one smelt job: state, exit code, run status, optional log tail. Read-only.",
    "smelt_jobs": "List recent smelt jobs, newest first. Read-only.",
    "smelt_kill": "Stop a running smelt job (whole process group). The run dir is kept for smelt resume.",
    "smelt_verify": "Verify a job's artifacts are fresh and terminal (mtime-checked, not just exit 0). Read-only.",
    "smelt_report": "Read a finished run's markdown report (every attempt incl. failures, measured speedup + CI). Read-only.",
    "smelt_apply": "Print the VIEW-ONLY diff + fallback shim for an accepted run. Never writes into the target repo.",
}

TOOL_SCHEMAS = {
    "smelt_scan": {"type": "object", "properties": {
        "path": {"type": "string", "description": "directory to scan for candidate functions"}},
        "required": ["path"]},
    "smelt_doctor": {"type": "object", "properties": {
        "probe": {"type": "boolean", "description": "send tiny live provider calls where keys exist"}}},
    "smelt_capture": {"type": "object", "properties": {
        "target": {"type": "string", "description": "path/to/file.py:function"},
        "cases": {"type": "integer", "description": "oracle size target (default 200)"},
        "seed": {"type": "integer"},
        "runs_dir": {"type": "string"}},
        "required": ["target"]},
    "smelt_run": {"type": "object", "properties": {
        "target": {"type": "string", "description": "path/to/file.py:function"},
        "provider": {"type": "string", "description": "nvidia|gemini|local|do|openai|openrouter|file|fake (default: auto from keys)"},
        "model": {"type": "string"},
        "max_attempts": {"type": "integer"},
        "cases": {"type": "integer"},
        "seed": {"type": "integer"},
        "repair": {"type": "boolean", "description": "evidence-fed attempts 2+ (default true)"},
        "candidate": {"type": "string", "description": "lib.rs path/glob for the file/fake providers (gate runs)"},
        "runs_dir": {"type": "string"}},
        "required": ["target"]},
    "smelt_job": {"type": "object", "properties": {
        "job_id": {"type": "string"},
        "tail": {"type": "integer", "description": "include the last N log lines"}},
        "required": ["job_id"]},
    "smelt_jobs": {"type": "object", "properties": {
        "limit": {"type": "integer"}}},
    "smelt_kill": {"type": "object", "properties": {
        "job_id": {"type": "string"}}, "required": ["job_id"]},
    "smelt_verify": {"type": "object", "properties": {
        "job_id": {"type": "string"}}, "required": ["job_id"]},
    "smelt_report": {"type": "object", "properties": {
        "run_dir": {"type": "string"}}, "required": ["run_dir"]},
    "smelt_apply": {"type": "object", "properties": {
        "run_dir": {"type": "string"}}, "required": ["run_dir"]},
}


def dispatch(name: str, args: dict) -> dict:
    h = HANDLERS.get(name)
    if h is None:
        return _err(f"unknown tool: {name}")
    try:
        return h(args or {})
    except AgentApiError as e:
        return _err(str(e))
    except Exception as e:  # surface boundary: errors are data
        return _err(f"{type(e).__name__}: {e}")
