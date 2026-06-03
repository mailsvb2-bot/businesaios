from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class SDKRequest:
    payload: Mapping[str, Any]

__all__ = [
    "SDKRequest",
]
