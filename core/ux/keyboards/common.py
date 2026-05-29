from __future__ import annotations

"""Common pure keyboard helpers."""

from typing import Any


def mk(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}
