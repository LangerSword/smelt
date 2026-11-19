"""Smelt plugin for Hermes: verified Python→Rust hotspot conversion.

One handler core (smelt_agent_api, a vendored copy of smelt_rs.agent_api —
synced by scripts/sync_plugin.py, byte-identical) drives the installed smelt
CLI. Long runs are detached jobs; mutating verbs are approval-gated via
pre_tool_call. Wiring uses the public plugin API: ctx.register_tool /
ctx.register_hook. The bundled skill (skills/smelt) is a synced COPY of the
repo's Agent-Skills-standard skill (the validator rejects symlinks escaping
the plugin root; scripts/sync_plugin.py keeps both in sync, CI checks drift).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__version__ = "0.8.0"

TOOLSET = "smelt"


def register(ctx) -> None:
    try:  # loaded as a Hermes plugin package
        from .smelt_hooks import pre_tool_call
        from .smelt_tools import TOOL_SPECS
    except ImportError:  # loaded standalone (smoke_load.py, tests)
        from smelt_hooks import pre_tool_call
        from smelt_tools import TOOL_SPECS

    ctx.register_hook("pre_tool_call", pre_tool_call)

    for spec in TOOL_SPECS:
        def tool_handler(args: dict, _run=spec["handler"], **_kw) -> str:
            return _run(args or {})

        ctx.register_tool(
            name=spec["name"],
            toolset=TOOLSET,
            schema=spec["schema"],
            handler=tool_handler,
            description=spec["description"],
            emoji=spec.get("emoji", "🔥"),
        )


__all__ = ["register", "__version__"]
