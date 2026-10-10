"""Safety scan + cargo build for UNTRUSTED generated Rust.

Two layers protect the machine and the repo:
1. Static scan (before anything compiles): banned patterns refuse the candidate.
2. Build isolation: a scratch crate dir, our pinned Cargo.toml, a dedicated target
   dir, and the generated code never touches the target project.
Reviewed closely by the developer (this is the sandbox boundary).
"""

import os
import re
import shutil
import subprocess

from smelt_rs.core.failures import BuildError, SafetyViolation
from smelt_rs.scaffold.templates import CARGO_TOML, CRATE_NAME

BANNED_PATTERNS = [
    ("unsafe block", r"\bunsafe\b"),
    ("std::process", r"std::process"),
    ("std::net", r"std::net"),
    ("std::fs", r"std::fs"),
    ("include_*! macros", r"include_(str|bytes)!"),
    ("env!/option_env!", r"\benv!|option_env!"),
    ("Command", r"\bCommand\b"),
    ("extern crate", r"^\s*extern\s+crate\b"),
    ("libc", r"\blibc\b"),
    ("OUT_DIR usage", r"\bOUT_DIR\b"),
]

MAX_LIB_BYTES = 200_000


def safety_scan(lib_rs: str, func_name: str) -> list[str]:
    """Return violations; empty list = safe to build."""
    violations: list[str] = []
    if len(lib_rs.encode()) > MAX_LIB_BYTES:
        violations.append("file too large (>200KB)")
    for label, pat in BANNED_PATTERNS:
        if re.search(pat, lib_rs, flags=re.MULTILINE):
            violations.append(f"banned pattern: {label}")
    if not re.search(rf"fn\s+{re.escape(func_name)}\s*\(", lib_rs):
        violations.append(f"missing required function `fn {func_name}(...)`")
    if "#[pyfunction]" not in lib_rs:
        violations.append("missing #[pyfunction] attribute")
    if not re.search(r"fn\s+smelt_ext\s*\(", lib_rs):
        violations.append("missing `#[pymodule] fn smelt_ext(...)` glue")
    return violations


def classify_build_error(stderr: str) -> str:
    if any(code in stderr for code in ("E0599", "E0277", "E0432", "E0433")):
        return "api_drift"
    if "error[E" in stderr or "error:" in stderr:
        return "compile_error"
    if "failed to fetch" in stderr or "network" in stderr.lower():
        return "network"
    return "unknown"


def build_crate(*, build_dir: str, lib_rs: str, func_name: str, python_exe: str,
                target_dir: str, timeout: int = 420) -> str:
    """Write the crate, scan, build. Returns the path to the built .so."""
    violations = safety_scan(lib_rs, func_name)
    if violations:
        rejected_dir = os.path.join(build_dir, "_rejected")
        os.makedirs(rejected_dir, exist_ok=True)
        with open(os.path.join(rejected_dir, "lib.rs"), "w") as f:
            f.write(lib_rs)
        raise SafetyViolation("safety scan failed: " + "; ".join(violations))

    src_dir = os.path.join(build_dir, "src")
    os.makedirs(src_dir, exist_ok=True)
    with open(os.path.join(build_dir, "Cargo.toml"), "w") as f:
        f.write(CARGO_TOML)
    with open(os.path.join(src_dir, "lib.rs"), "w") as f:
        f.write(lib_rs)

    cargo = shutil.which("cargo")
    if not cargo:
        raise BuildError("cargo not found on PATH — install Rust (rustup) first", subkind="no_cargo")

    env = dict(os.environ)
    env["CARGO_TARGET_DIR"] = target_dir
    env["PYO3_PYTHON"] = python_exe
    p = subprocess.run([cargo, "build", "--release"], cwd=build_dir, capture_output=True,
                       text=True, timeout=timeout, env=env)
    if p.stderr:
        with open(os.path.join(build_dir, "cargo_stderr.txt"), "w") as f:
            f.write(p.stderr[-20000:])
    if p.returncode != 0:
        raise BuildError("cargo build failed", details=p.stderr[-3000:],
                         subkind=classify_build_error(p.stderr))
    so_path = os.path.join(target_dir, "release", f"lib{CRATE_NAME}.so")
    if not os.path.exists(so_path):
        raise BuildError("built library not found at expected path", subkind="missing_artifact")
    return so_path
