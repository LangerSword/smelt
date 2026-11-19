"""smelt MCP server — stdio JSON-RPC, stdlib only (no extra dependencies).

Exposes the agent_api handlers as MCP tools so ANY MCP-capable coding agent
(Claude Code, Cursor, OpenCode, Hermes, Goose, ...) can drive smelt:

    smelt mcp                     # or: python -m smelt_rs.mcp_server

Protocol: MCP stdio transport (newline-delimited JSON-RPC 2.0). Implements
initialize (version negotiation), ping, tools/list, tools/call; notifications
are accepted without response. stdout is ONLY the protocol channel — all
diagnostics go to stderr (SMELT_MCP_DEBUG=1 for a trace).

Tool results are the agent_api dicts rendered as JSON text content; a handler
error sets isError=true so the agent sees a correctable failure, never a crash.
"""

import json
import os
import sys

from smelt_rs.agent_api import HANDLERS, TOOL_DESCRIPTIONS, TOOL_SCHEMAS, dispatch
from smelt_rs.core.state import SMELT_VERSION

SUPPORTED_PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")
LATEST_PROTOCOL = "2025-06-18"


def _debug(msg: str) -> None:
    if os.environ.get("SMELT_MCP_DEBUG"):
        print(f"[smelt-mcp] {msg}", file=sys.stderr, flush=True)


def _result(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_message(msg: dict) -> dict | None:
    """One JSON-RPC message in, one response out (None for notifications)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _error(msg.get("id") if isinstance(msg, dict) else None,
                      -32600, "invalid request")
    method = msg.get("method", "")
    req_id = msg.get("id")
    is_notification = "id" not in msg
    params = msg.get("params") or {}

    if method == "initialize":
        client_proto = params.get("protocolVersion")
        proto = client_proto if client_proto in SUPPORTED_PROTOCOLS else LATEST_PROTOCOL
        return _result(req_id, {
            "protocolVersion": proto,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "smelt", "version": SMELT_VERSION},
            "instructions": "smelt converts ONE slow pure Python function into a verified "
                            "Rust extension. Code, not the model, accepts: frozen oracle, "
                            "safety scan, 100% case verification, measured speedup with a "
                            "conservative 1.5x lower bound. smelt_run is detached — poll "
                            "smelt_job, then smelt_verify + smelt_report. Refusals and "
                            "rejections are correct outcomes, not errors.",
        })
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return _result(req_id, {})
    if method == "tools/list":
        tools = [{"name": name, "description": TOOL_DESCRIPTIONS.get(name, ""),
                  "inputSchema": TOOL_SCHEMAS.get(name, {"type": "object", "properties": {}})}
                 for name in HANDLERS]
        return _result(req_id, {"tools": tools})
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        if name not in HANDLERS:
            return _result(req_id, {"content": [{"type": "text",
                                                 "text": json.dumps({"ok": False, "error": f"unknown tool: {name}"})}],
                                    "isError": True})
        out = dispatch(name, args)
        return _result(req_id, {"content": [{"type": "text", "text": json.dumps(out, default=str)}],
                                "isError": not out.get("ok", False)})
    if is_notification:
        return None  # unknown notification: ignore per JSON-RPC
    return _error(req_id, -32601, f"method not found: {method}")


def serve(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    _debug(f"serving (smelt {SMELT_VERSION}, protocol {LATEST_PROTOCOL})")
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = _error(None, -32700, "parse error")
        else:
            try:
                resp = handle_message(msg)
            except Exception as e:  # never kill the transport
                _debug(f"handler crash: {e!r}")
                resp = _error(msg.get("id") if isinstance(msg, dict) else None,
                              -32603, f"internal error: {type(e).__name__}")
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
    _debug("stdin closed — exiting")


if __name__ == "__main__":
    serve()
