from __future__ import annotations

"""Common pure keyboard helpers."""

from typing import Any, Dict, List


def mk(rows: List[List[Dict[str, str]]]) -> Dict[str, Any]:
    return {"inline_keyboard": rows}
