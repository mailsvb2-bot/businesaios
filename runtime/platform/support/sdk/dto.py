from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SDKRequest:
    payload: Mapping[str, Any]

__all__ = [
    "SDKRequest",
]
