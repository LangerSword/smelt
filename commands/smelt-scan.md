---
description: Scan a directory for smelt-able hot Python functions (pure, supported types)
argument-hint: [path]
allowed-tools: Bash(smelt scan:*), Bash(smelt doctor:*)
---

Run `smelt scan ${ARGUMENTS:-.} --json` and summarize the result for the user:

- List the tier-1 candidates (file:function, parameter types) — these are pure
  functions smelt can attempt to convert to verified Rust.
- Group the skips by reason (impure, unsupported type, unresolvable import) and
  show the refactor hints — refusals are correct outcomes, not errors.
- If there are candidates, offer the next step: `/smelt-run <file.py:function>`
  for the hottest one. Do NOT start a run without the user asking.
- If `smelt` is not on PATH, say so and point at `uv tool install smelt-rs` or
  the repo quickstart; do not improvise an install.
