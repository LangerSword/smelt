"""MCP server (v0.8): protocol unit tests + a real stdio round-trip.

The end-to-end test spawns `python -m smelt_rs.mcp_server` and speaks
newline-delimited JSON-RPC to it — the same transport any MCP agent uses.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from smelt_rs import mcp_server as M  # noqa: E402
from smelt_rs.agent_api import HANDLERS  # noqa: E402


def test_initialize_negotiates_known_protocol():
    for proto in M.SUPPORTED_PROTOCOLS:
        resp = M.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                 "params": {"protocolVersion": proto}})
        assert resp["result"]["protocolVersion"] == proto
        assert resp["result"]["serverInfo"]["name"] == "smelt"
        assert "tools" in resp["result"]["capabilities"]


def test_initialize_unknown_protocol_falls_back():
    resp = M.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "1999-01-01"}})
    assert resp["result"]["protocolVersion"] == M.LATEST_PROTOCOL


def test_tools_list_matches_handlers():
    resp = M.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = resp["result"]["tools"]
    assert sorted(t["name"] for t in tools) == sorted(HANDLERS)
    for t in tools:
        assert t["description"] and t["inputSchema"]["type"] == "object"


def test_notifications_get_no_response():
    assert M.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert M.handle_message({"jsonrpc": "2.0", "method": "some/unknown/notification"}) is None


def test_ping_and_unknown_method():
    assert M.handle_message({"jsonrpc": "2.0", "id": 3, "method": "ping"})["result"] == {}
    resp = M.handle_message({"jsonrpc": "2.0", "id": 4, "method": "no/such/method"})
    assert resp["error"]["code"] == -32601


def test_invalid_request():
    resp = M.handle_message({"hello": "world"})
    assert resp["error"]["code"] == -32600


def test_tools_call_bad_input_is_tool_error():
    resp = M.handle_message({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                             "params": {"name": "smelt_scan", "arguments": {}}})
    assert resp["result"]["isError"] is True
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["ok"] is False and "error" in payload


def test_tools_call_unknown_tool():
    resp = M.handle_message({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                             "params": {"name": "smelt_nope", "arguments": {}}})
    assert resp["result"]["isError"] is True


def test_stdio_roundtrip(tmp_path):
    """Spawn the real server; initialize -> tools/list -> tools/call(scan)."""
    (tmp_path / "demo.py").write_text("def shout(s: str) -> str:\n    return s.upper()\n")
    env = dict(os.environ)
    env["SMELT_BIN"] = str(REPO / ".venv/bin/smelt")
    env["SMELT_JOBS_DIR"] = str(tmp_path / "jobs")
    env["PYTHONPATH"] = str(REPO / "src")
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "smelt_scan", "arguments": {"path": str(tmp_path)}}},
    ]
    stdin = "\n".join(json.dumps(m) for m in messages) + "\n"
    p = subprocess.run([sys.executable, "-m", "smelt_rs.mcp_server"],
                       input=stdin, capture_output=True, text=True, timeout=60, env=env,
                       cwd=str(REPO))
    assert p.returncode == 0, p.stderr[-500:]
    lines = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
    assert len(lines) == 3, f"expected 3 responses (notification silent), got {len(lines)}"
    assert lines[0]["id"] == 1 and lines[0]["result"]["serverInfo"]["name"] == "smelt"
    assert lines[1]["id"] == 2 and len(lines[1]["result"]["tools"]) == len(HANDLERS)
    assert lines[2]["id"] == 3
    payload = json.loads(lines[2]["result"]["content"][0]["text"])
    assert payload["ok"], payload
    assert any(c["function"] == "shout" for c in payload["candidates"])
    # stdout carried ONLY protocol JSON — no stray prints
    for l in p.stdout.splitlines():
        if l.strip():
            json.loads(l)
