from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def read_payload(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
