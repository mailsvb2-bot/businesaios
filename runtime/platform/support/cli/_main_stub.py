from __future__ import annotations

import sys
from collections.abc import Sequence

from runtime.platform.support.cli.commands import build_cli_implementations
from runtime.platform.support.cli.registry import CLI_COMMANDS
from runtime.platform.support.entrypoint_contract import build_entrypoint_spec, dispatch_entrypoint

CLI_ENTRYPOINT = build_entrypoint_spec(surface_label="CLI", audit_surface="cli", commands=CLI_COMMANDS)


def cli_main(command: str, argv: Sequence[str] | None = None) -> int:
    return dispatch_entrypoint(
        command,
        spec=CLI_ENTRYPOINT,
        implementations=build_cli_implementations(argv if argv is not None else tuple(sys.argv[1:])),
    )

__all__ = [
    "CLI_COMMANDS",
    "CLI_ENTRYPOINT",
    "cli_main",
]
