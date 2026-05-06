from __future__ import annotations

"""Structured observability for platform-support command entrypoints.

The platform-support surface still carries honest no-op shims for packaging stability.
This module makes those invocations inspectable instead of only printing to stderr.
"""

import json
import os
from pathlib import Path
from typing import Mapping


def _audit_path() -> Path | None:
    raw = str(os.getenv("BUSINESAIOS_COMMAND_AUDIT_PATH", "")).strip()
    return Path(raw) if raw else None


def build_command_audit_record(*, surface: str, command: str, implemented: bool, exit_code: int) -> dict[str, object]:
    return {
        "surface": str(surface),
        "command": str(command),
        "implemented": bool(implemented),
        "exit_code": int(exit_code),
    }


def emit_command_audit(record: Mapping[str, object]) -> None:
    path = _audit_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(record), sort_keys=True) + "\n")


__all__ = ["build_command_audit_record", "emit_command_audit"]
