# Safety

Generated Rust is **untrusted code**. smelt treats it that way:

1. **Pinned scaffold** — the crate and `Cargo.toml` are supplied by smelt
   (pyo3 `=0.29.3`); the model fills in one function body.
2. **Static scan before build** — rejects `unsafe`, extra crates, `build.rs`,
   `std::net`/`std::process`/`std::fs`, `include_*!`, `env!`.
3. **Isolated execution** — builds happen in run-scratch directories; the
   built extension executes in a separate worker process with resource limits.
   The worker records outcomes (including Rust panics, converted to Python
   exceptions) and never aborts the pipeline.
4. **smelt never writes into your project** — outputs are run artifacts and
   reports. `smelt apply` is VIEW ONLY (a diff plus a try/except fallback shim);
   applying the change stays a manual, reviewed step.
5. **Secrets** — never printed, logged, or committed. Keys come from the
   environment or untracked `.env` files. `smelt doctor` reports key presence,
   never values. `--probe` sends tiny live calls only where a key exists.
6. **Furnace (the TUI)** — a front end only: it reads `events.jsonl` and starts
   `smelt run --json` as a subprocess. It never runs generated code and never
   reads secrets. Quitting mid-run kills the whole process group (no orphan
   cargo/worker processes) and prints the `smelt resume` command.
