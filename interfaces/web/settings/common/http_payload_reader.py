from __future__ import annotations

from typing import Any, Mapping


def read_payload(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
