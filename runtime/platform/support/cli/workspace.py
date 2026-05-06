from __future__ import annotations

"""Shared local workspace helpers for platform-support CLI commands."""

import os
from pathlib import Path


def support_workspace_root() -> Path:
    raw = str(os.getenv("BUSINESAIOS_PLATFORM_SUPPORT_DIR", "")).strip()
    if raw:
        path = Path(raw)
    else:
        path = Path.cwd() / ".businesaios" / "platform_support"
    path.mkdir(parents=True, exist_ok=True)
    return path


def workspace_path(*parts: str) -> Path:
    path = support_workspace_root().joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["support_workspace_root", "workspace_path"]
