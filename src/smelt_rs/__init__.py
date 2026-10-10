"""smelt — turn one slow pure Python function into a verified Rust extension.

Package layout (L0):
  core/       — orchestrator, state/events, typed failures, purity probe
  oracle/     — case generation, capture/freeze, verification
  scaffold/   — pinned pyo3 templates (golden example)
  build/      — safety scan, cargo build, sandboxed worker
  bench/      — timing protocol and decision rules
  providers/  — where candidate Rust comes from
"""

__version__ = "0.1.0"
