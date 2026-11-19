"""Tool surface: ten verbs over the shared agent_api core (JSON in, JSON out)."""

from __future__ import annotations

import json

try:  # loaded as a Hermes plugin package
    from . import smelt_agent_api as A
except ImportError:  # loaded standalone (tests, scripts)
    import smelt_agent_api as A


def _j(obj) -> str:
    return json.dumps(obj, indent=1, default=str)


def _make_handler(name: str):
    def handler(args: dict) -> str:
        return _j(A.dispatch(name, args or {}))
    return handler


TOOL_SPECS = [
    {"name": name,
     "schema": A.TOOL_SCHEMAS[name],
     "description": A.TOOL_DESCRIPTIONS[name],
     "handler": _make_handler(name),
     "emoji": "🔥"}
    for name in A.HANDLERS
]

TOOL_NAMES = [spec["name"] for spec in TOOL_SPECS]
