from __future__ import annotations

from collections.abc import Iterable


def normalize_command_name(command: str | None, *, default: str = "") -> str:
    text = str(command or "").strip().replace("-", "_")
    return text or str(default or "")


def known_command_set(commands: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for command in commands:
        normalized = normalize_command_name(command)
        if normalized and normalized not in seen:
            ordered.append(normalized)
            seen.add(normalized)
    return tuple(ordered)


def is_known_command(command: str | None, *, commands: Iterable[str]) -> bool:
    return normalize_command_name(command) in set(known_command_set(commands))


def require_known_command(command: str | None, *, commands: Iterable[str], surface: str) -> str:
    normalized = normalize_command_name(command)
    if normalized not in set(known_command_set(commands)):
        raise RuntimeError(f"Unknown {surface} command: {normalized or '<empty>'}")
    return normalized


__all__ = [
    "normalize_command_name",
    "known_command_set",
    "is_known_command",
    "require_known_command",
]
