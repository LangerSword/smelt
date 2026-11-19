# smelt plugin for Hermes

Verified Python→Rust hotspot conversion as a Hermes plugin: **10 tools, 1 hook,
1 bundled skill** — all over one stdlib-only handler core (`smelt_agent_api.py`,
a byte-identical vendored copy of `src/smelt_rs/agent_api.py`, synced by
`scripts/sync_plugin.py`).

## Install

```bash
# requires the smelt CLI (uv tool install smelt-rs, or a checkout on PATH)
ln -s /path/to/smelt/plugin ~/.hermes/plugins/smelt
hermes plugins validate ~/.hermes/plugins/smelt
hermes plugins enable smelt
```

Tools land in the next session; the `pre_tool_call` hook hot-reloads. The
bundled skill (`skills/smelt`, a synced copy of the repo's Agent-Skills-
standard skill — `scripts/sync_plugin.py` keeps them identical) teaches the
agent the loop and the honest-outcome semantics.

`hermes plugins validate` passes; its one caution (`inline_shell_exec` in
SKILL.md) is the skill's documented CLI usage examples — teaching shell
commands is the skill's purpose, not an execution path in the plugin.

## Surface

| tool | what it does | gate |
|---|---|---|
| `smelt_scan` | list candidates with tier + skip reasons | read-only |
| `smelt_doctor` | toolchain + provider checks (`probe` for live calls) | read-only |
| `smelt_capture` | freeze an oracle by RUNNING the target (no model) | **approval** |
| `smelt_run` | full loop as a **detached job** — returns a job_id immediately | **approval** |
| `smelt_job` / `smelt_jobs` | poll one / list recent (newest first), log tail | read-only |
| `smelt_kill` | stop a job's whole process group (run dir kept for resume) | **approval** |
| `smelt_verify` | artifacts fresh + terminal (mtime-checked, not just exit 0) | read-only |
| `smelt_report` | the run's honest markdown report | read-only |
| `smelt_apply` | VIEW-ONLY diff + fallback shim; never writes the repo | read-only |

`pre_tool_call` returns an approve card naming the exact target/job for the
three mutating verbs; denial or timeout fails closed. Read-only verbs pass
silently; foreign tools are untouched.

## Security notes

- Job children get an **allowlisted environment** (PATH/HOME/locale/SMELT_*
  config) plus **exactly the provider-key names smelt resolves**
  (NVIDIA_API_KEY, GEMINI_API_KEY, GOOGLE_API_KEY, DIGITALOCEAN_TOKEN,
  SMELT_OPENAI_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, SMELT_PROVIDER_KEY).
  The host's other secrets never reach a job; dropped secret-like names are
  recorded in the job meta (names only, never values). This forwarding is
  deliberate — the product cannot call a provider without its key — and
  bounded to the names the provider layer actually looks up.
- Generated Rust stays untrusted: smelt's own safety scan + sandboxed worker
  apply inside every run, unchanged by the plugin layer.
- Job artifacts live under `SMELT_JOBS_DIR` (default `~/.cache/smelt/jobs`);
  job ids are validated against path escape.

## Prove it without Hermes

```bash
python3 scripts/sync_plugin.py --check   # vendored core in sync
python3 plugin/smoke_load.py             # register + hook dispatch + real handler
```

`smoke_load.py` loads the plugin as a package against a recording ctx, asserts
declared == registered, dispatches the approval hook with real payloads, and
drives `smelt_scan` through the registered handler against the real CLI.
