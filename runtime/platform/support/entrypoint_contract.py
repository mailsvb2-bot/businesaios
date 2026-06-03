from __future__ import annotations

"""Shared contract for platform-support CLI and script entrypoints.

Keeps command normalization and dispatch in one place so CLI and script surfaces do not
carry subtly different validation or execution paths.
"""

from dataclasses import dataclass
from typing import Callable
from collections.abc import Iterable, Mapping

from runtime.platform.support._command_surface import run_named_command
from runtime.platform.support.command_registry import require_known_command

ImplementationMap = Mapping[str, Callable[[], int]]


@dataclass(frozen=True)
class CommandEntrypointSpec:
    surface_label: str
    audit_surface: str
    commands: tuple[str, ...]


def dispatch_entrypoint(
    command: str,
    *,
    spec: CommandEntrypointSpec,
    implementations: ImplementationMap | None = None,
) -> int:
    normalized = require_known_command(command, commands=spec.commands, surface=spec.surface_label)
    return run_named_command(surface=spec.audit_surface, command=normalized, implementations=implementations)


def build_entrypoint_spec(*, surface_label: str, audit_surface: str, commands: Iterable[str]) -> CommandEntrypointSpec:
    return CommandEntrypointSpec(
        surface_label=str(surface_label),
        audit_surface=str(audit_surface),
        commands=tuple(str(command) for command in commands),
    )


__all__ = ["CommandEntrypointSpec", "ImplementationMap", "build_entrypoint_spec", "dispatch_entrypoint"]
