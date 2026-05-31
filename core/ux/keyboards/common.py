"""Common pure keyboard helpers."""

from __future__ import annotations

from typing import Any


def mk(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}
