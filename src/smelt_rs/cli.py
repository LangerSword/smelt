"""smelt CLI — run / capture / resume / report / doctor.

Exit codes: 0 accepted (or capture ok) · 2 config error · 3 refused (impure target) ·
4 rejected (no acceptable rewrite — a correct, honest result) · 5 harness/internal error.

`--json` prints a machine-readable summary instead of human progress lines (CI use).
"""

import json
import os
import platform
import shutil
import sys
import urllib.error
import urllib.request

import typer
from rich import print as rprint
from rich.table import Table

from smelt_rs.core import orchestrator

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="Smelt a slow pure Python function into a verified Rust extension. "
                       "Only proven metal ships.")


@app.command()
def run(target: str,
        provider: str = typer.Option("local", help="local | gemini | do | openai | file | fake"),
        model: str = typer.Option(None, help="model name for the provider"),
        candidate: str = typer.Option(None, help="candidate lib.rs path (file/fake providers)"),
        runs_dir: str = typer.Option("runs", help="directory for run artifacts"),
        max_attempts: int = typer.Option(3, help="generation attempts cap"),
        cases: int = typer.Option(200, help="oracle size target"),
        seed: int = typer.Option(None, help="oracle generation seed"),
        bench_min_ms: int = typer.Option(100, help="minimum python-side workload per rep (ms)"),
        json_out: bool = typer.Option(False, "--json", help="machine-readable output")):
    """Run the full smelt loop on one function: path/to/file.py:function"""
    code, info = orchestrator.run(target=target, provider_name=provider, model=model,
                                  candidate=candidate, runs_dir=runs_dir,
                                  max_attempts=max_attempts, target_cases=cases, seed=seed,
                                  bench_min_s=bench_min_ms / 1000, quiet=json_out)
    if json_out:
        print(json.dumps(info, default=str))
    raise typer.Exit(code)


@app.command()
def capture(target: str,
            runs_dir: str = typer.Option("runs", help="directory for run artifacts"),
            cases: int = typer.Option(200, help="oracle size target"),
            seed: int = typer.Option(None, help="oracle generation seed"),
            json_out: bool = typer.Option(False, "--json", help="machine-readable output")):
    """Capture + freeze the oracle only (no generation, no build)."""
    code, info = orchestrator.capture_only(target=target, runs_dir=runs_dir,
                                           target_cases=cases, seed=seed, quiet=json_out)
    if json_out:
        print(json.dumps(info, default=str))
    raise typer.Exit(code)


@app.command()
def resume(run_dir: str,
           max_attempts: int = typer.Option(3, help="attempt cap (>= attempts already made)"),
           json_out: bool = typer.Option(False, "--json", help="machine-readable output")):
    """Resume an interrupted run from its checkpoint."""
    code, info = orchestrator.resume(run_dir=run_dir, max_attempts=max_attempts, quiet=json_out)
    if json_out:
        print(json.dumps(info, default=str))
    raise typer.Exit(code)


@app.command()
def report(run_dir: str):
    """Print a run's report (markdown)."""
    path = os.path.join(run_dir, "report.md")
    if not os.path.exists(path):
        rprint(f"[red]no report at {path}[/red]")
        raise typer.Exit(2)
    rprint(open(path).read())


def _probe_gemini(key: str):
    body = json.dumps({"contents": [{"parts": [{"text": "Reply with exactly one word: OK"}]}]}).encode()
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent",
        data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, "gemma-4-31b-it answered"
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read()[:120].decode(errors="replace")
        except Exception:
            pass
        return False, f"HTTP {e.code}: {detail[:80]}"
    except Exception as e:
        return False, repr(e)[:80]


def _probe_do(token: str):
    req = urllib.request.Request("https://inference.do-ai.run/v1/models",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return True, "inference.do-ai.run reachable"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, repr(e)[:80]


@app.command()
def doctor(probe: bool = typer.Option(False, "--probe", help="send tiny live test calls where keys exist"),
           json_out: bool = typer.Option(False, "--json", help="machine-readable output")):
    """Check toolchain, sandbox, local server, and provider keys. Green = no FAIL rows."""
    from smelt_rs.providers.providers import resolve_secret
    from smelt_rs.worker_client import run_worker

    rows = []

    def add(name, ok, detail="", required=True):
        rows.append({"name": name, "ok": bool(ok), "detail": detail, "required": required})

    add("python", sys.version_info >= (3, 11), platform.python_version())
    cargo = shutil.which("cargo")
    add("cargo", bool(cargo), cargo or "not on PATH — install Rust (rustup)")
    rustc = shutil.which("rustc")
    add("rustc", bool(rustc), rustc or "missing", required=False)
    maturin = shutil.which("maturin")
    add("maturin", bool(maturin), maturin or "missing (packaging only)", required=False)

    worker_ok, worker_detail = False, ""
    try:
        res = run_worker(sys.executable, {"mode": "doctor-ping"}, timeout=30)
        worker_ok = isinstance(res, dict) and str(res.get("error", "")).startswith("unknown mode")
        worker_detail = "protocol ok" if worker_ok else f"unexpected: {str(res)[:80]}"
    except Exception as e:
        worker_detail = repr(e)[:100]
    add("sandbox worker", worker_ok, worker_detail)

    target_dir = os.environ.get("SMELT_TARGET_DIR", os.path.expanduser("~/.cache/smelt/target"))
    try:
        os.makedirs(target_dir, exist_ok=True)
        probe_file = os.path.join(target_dir, ".smelt-write-test")
        with open(probe_file, "w") as f:
            f.write("x")
        os.remove(probe_file)
        add("cargo target dir", True, target_dir)
    except Exception as e:
        add("cargo target dir", False, f"{target_dir}: {e!r}")

    local_up = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=3) as r:
            local_up = r.status == 200
    except Exception:
        pass
    add("local model server", local_up,
        "http://127.0.0.1:8080" if local_up else "not reachable (start llama-server)", required=False)

    gkey = resolve_secret("GEMINI_API_KEY")
    add("gemini key", bool(gkey),
        "present (GEMINI_API_KEY)" if gkey else "missing — set GEMINI_API_KEY", required=False)
    dtoken = resolve_secret("DIGITALOCEAN_TOKEN")
    add("digitalocean token", bool(dtoken),
        "present (DIGITALOCEAN_TOKEN)" if dtoken else "missing — set DIGITALOCEAN_TOKEN", required=False)
    okey = resolve_secret("SMELT_OPENAI_KEY")
    add("openai-compat key", bool(okey), "present" if okey else "not set (optional)", required=False)

    if probe:
        if gkey:
            ok, detail = _probe_gemini(gkey)
            add("gemini probe", ok, detail, required=False)
        if dtoken:
            ok, detail = _probe_do(dtoken)
            add("do probe", ok, detail, required=False)

    fails = [r for r in rows if not r["ok"] and r["required"]]
    warns = [r for r in rows if not r["ok"] and not r["required"]]
    if json_out:
        print(json.dumps({"checks": rows, "fails": len(fails), "warns": len(warns)}))
    else:
        table = Table(title="smelt doctor")
        table.add_column("check")
        table.add_column("status")
        table.add_column("detail")
        for r in rows:
            status = "[green]✓[/green]" if r["ok"] else ("[red]✗[/red]" if r["required"] else "[yellow]warn[/yellow]")
            table.add_row(r["name"], status, r["detail"])
        rprint(table)
        if fails:
            rprint(f"[red]{len(fails)} required check(s) failed[/red]")
        elif warns:
            rprint(f"[yellow]{len(warns)} warning(s) — not blocking[/yellow]")
        else:
            rprint("[green]all checks green[/green]")
    raise typer.Exit(1 if fails else 0)


def main():
    app()


if __name__ == "__main__":
    main()
