# Agent integration — smelt as a plugin anywhere

smelt ships one handler core (`src/smelt_rs/agent_api.py`, stdlib only) behind
three agent surfaces. All of them drive the same CLI and the same gates —
there is no second implementation to drift.

## 1. MCP server — any MCP-capable agent

```bash
smelt mcp        # stdio JSON-RPC; zero extra dependencies
```

Wire it into your agent's MCP config:

```json
{"mcpServers": {"smelt": {"command": "smelt", "args": ["mcp"]}}}
```

- **Claude Code**: `claude mcp add smelt -- smelt mcp` (or the repo's
  `.mcp.json` when installed as a plugin).
- **Cursor / Windsurf / Goose / OpenCode / Hermes**: the same
  `command`/`args` pair in their MCP settings (`hermes mcp add smelt
  --command smelt --arg mcp`).

Tools: `smelt_scan`, `smelt_doctor`, `smelt_capture`, `smelt_run` (detached
job), `smelt_job`, `smelt_jobs`, `smelt_kill`, `smelt_verify`, `smelt_report`,
`smelt_apply`. Protocol: initialize (version negotiation 2024-11-05 /
2025-03-26 / 2025-06-18), ping, tools/list, tools/call. Handler errors come
back as `isError` tool results — correctable data, never a crashed transport.

`smelt_run` returns a **job id immediately**; the run survives the agent call
(child in its own session, log + child-written exit code). Poll `smelt_job`,
then `smelt_verify` (fresh, terminal artifacts — mtime-checked) and
`smelt_report`. `smelt_kill` stops the whole process group; the run dir stays
resumable.

## 2. Hermes plugin

`plugin/` — 10 tools + a `pre_tool_call` approval hook + the bundled skill.
Install and security notes: [`plugin/README.md`](../plugin/README.md).

```bash
ln -s /path/to/smelt/plugin ~/.hermes/plugins/smelt
hermes plugins enable smelt
```

Mutating verbs (`smelt_run`, `smelt_capture`, `smelt_kill`) show an approval
card naming the exact target/job; read-only verbs pass silently.

## 3. Claude Code plugin (this repo)

The repo root is a Claude Code plugin: `.claude-plugin/plugin.json`,
`commands/` (`/smelt-scan`, `/smelt-run`, `/smelt-report`), `hooks/`
(PostToolUse: after a Python edit, quietly surface smelt-able candidates in
that file — never runs anything unprompted), `skills/smelt` (Agent Skills
open standard), and `.mcp.json` (the MCP server above).

```bash
claude plugin install /path/to/smelt     # or add as a marketplace/local plugin
```

## 4. Any other coding agent

- **Agent Skills**: `skills/smelt/SKILL.md` is validated against the Agent
  Skills open standard — copy it into any skills-compatible agent.
- **Plain CLI**: every verb is scriptable with `--json` and typed exit codes
  (0 accepted · 2 config · 3 refused · 4 rejected · 5 harness error). An agent
  that can run a shell can drive smelt with no integration at all.

## What every surface inherits

The gates are the product, not the wrapper: frozen differential oracle,
static safety scan before build, sandboxed worker, 100% case verification
(outcome parity + value equality + container fidelity), measured speedup with
a conservative 1.5x lower bound, repair evidence on attempts 2+, and honest
refusals/rejections. No surface can accept a rewrite the core would reject.
