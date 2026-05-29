from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class AttributionModel(str, Enum):
    FIRST_TOUCH = "first_touch"
    LAST_TOUCH = "last_touch"
    LINEAR = "linear"
    TIME_DECAY = "time_decay"

@dataclass(frozen=True)
class Touchpoint:
    ts_iso: str
    utm: dict[str, str]
    ads: dict[str, str]
