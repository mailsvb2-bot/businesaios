from __future__ import annotations

from runtime.platform.support.command_catalog import SCRIPT_COMMANDS
from runtime.platform.support.entrypoint_contract import build_entrypoint_spec, dispatch_entrypoint

SCRIPT_ENTRYPOINT = build_entrypoint_spec(surface_label="script", audit_surface="script", commands=SCRIPT_COMMANDS)


def script_main(command: str) -> int:
    return dispatch_entrypoint(command, spec=SCRIPT_ENTRYPOINT)

__all__ = [
    "SCRIPT_COMMANDS",
    "SCRIPT_ENTRYPOINT",
    "script_main",
]
