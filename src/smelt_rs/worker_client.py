"""Client for the sandboxed worker subprocess.

The worker runs untrusted-adjacent code (the target function; later the generated
extension) in a separate process with resource limits. One JSON request in, one
JSON response out. A non-zero exit or unparsable output is a typed VerifyCrash —
never silently ignored.
"""

import json
import os
import subprocess

from smelt_rs.core.failures import VerifyCrash


def worker_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "worker.py")


def run_worker(python_exe: str, req: dict, timeout: int = 180) -> dict:
    p = subprocess.run([python_exe, worker_path()], input=json.dumps(req),
                       capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise VerifyCrash(f"worker failed rc={p.returncode}: {(p.stderr or '')[-300:]}")
    try:
        return json.loads(p.stdout)
    except Exception as e:
        raise VerifyCrash(f"worker output unparsable: {e!r}: {(p.stdout or '')[:200]!r}")
