"""smelt CLI — run / resume / report.

Exit codes: 0 accepted · 2 config error · 3 refused (impure target) · 4 rejected
(no acceptable rewrite — a correct, honest result) · 5 harness/internal error.
"""

import os

import typer
from rich import print as rprint

from smelt_rs.core import orchestrator

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="Smelt a slow pure Python function into a verified Rust extension. "
                       "Only proven metal ships.")


@app.command()
def run(target: str,
        provider: str = typer.Option("local", help="provider: 'local' (OpenAI-compatible) or 'file'"),
        model: str = typer.Option(None, help="model name for the provider"),
        candidate: str = typer.Option(None, help="candidate lib.rs path (for --provider file)"),
        runs_dir: str = typer.Option("runs", help="directory for run artifacts"),
        max_attempts: int = typer.Option(3, help="generation attempts cap"),
        cases: int = typer.Option(200, help="oracle size target"),
        seed: int = typer.Option(None, help="oracle generation seed"),
        bench_min_ms: int = typer.Option(100, help="minimum python-side workload per rep (ms)")):
    """Run the full smelt loop on one function: path/to/file.py:function"""
    code = orchestrator.run(target=target, provider_name=provider, model=model, candidate=candidate,
                            runs_dir=runs_dir, max_attempts=max_attempts, target_cases=cases,
                            seed=seed, bench_min_s=bench_min_ms / 1000)
    raise typer.Exit(code)


@app.command()
def resume(run_dir: str, max_attempts: int = typer.Option(3, help="attempt cap (>= attempts already made)")):
    """Resume an interrupted run from its checkpoint."""
    code = orchestrator.resume(run_dir=run_dir, max_attempts=max_attempts)
    raise typer.Exit(code)


@app.command()
def report(run_dir: str):
    """Print a run's report (markdown)."""
    path = os.path.join(run_dir, "report.md")
    if not os.path.exists(path):
        rprint(f"[red]no report at {path}[/red]")
        raise typer.Exit(2)
    rprint(open(path).read())


def main():
    app()


if __name__ == "__main__":
    main()
