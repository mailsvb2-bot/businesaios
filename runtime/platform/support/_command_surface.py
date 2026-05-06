from __future__ import annotations

"""Canonical entrypoints for platform_support surfaces.

These modules intentionally stay thin, but no longer pretend to be full-featured
commands. Every entrypoint returns structured, explicit metadata describing the
requested command and whether a real implementation was wired.

Default behavior preserves historical packaging semantics by returning success
for known-but-unimplemented commands. Operators may opt into fail-closed entry
surfaces by setting ``BUSINESAIOS_PLATFORM_SUPPORT_STRICT_ENTRYPOINTS=1``.
"""

from dataclasses import dataclass
from typing import Callable, Mapping
import os
import sys

from runtime.platform.support.command_audit import build_command_audit_record, emit_command_audit


@dataclass(frozen=True)
class CommandResult:
    command: str
    surface: str
    implemented: bool
    exit_code: int = 0


ImplementationMap = Mapping[str, Callable[[], int]]


_MISSING_IMPLEMENTATION_EXIT_CODE = 78


def _strict_entrypoints_enabled() -> bool:
    token = str(os.getenv("BUSINESAIOS_PLATFORM_SUPPORT_STRICT_ENTRYPOINTS", "")).strip().lower()
    return token in {"1", "true", "yes", "y", "on"}


def _record(surface: str, command: str, implemented: bool, exit_code: int) -> None:
    os.environ[f"BUSINESAIOS_{surface.upper()}_LAST_COMMAND"] = str(command)
    emit_command_audit(
        build_command_audit_record(
            surface=surface,
            command=command,
            implemented=implemented,
            exit_code=exit_code,
        )
    )


def _missing_implementation_exit_code() -> int:
    return _MISSING_IMPLEMENTATION_EXIT_CODE if _strict_entrypoints_enabled() else 0


def run_named_command(*, surface: str, command: str, implementations: ImplementationMap | None = None) -> int:
    impl = dict(implementations or {}).get(command)
    if impl is not None:
        exit_code = int(impl())
        _record(surface, command, True, exit_code)
        return exit_code

    exit_code = _missing_implementation_exit_code()
    message = (
        f"[platform_support:{surface}] command '{command}' has no bundled implementation; "
        f"returning {'strict failure' if exit_code else 'no-op success'}.\n"
    )
    sys.stderr.write(message)
    _record(surface, command, False, exit_code)
    return exit_code

__all__ = [
    "CommandResult",
    "run_named_command",
]
