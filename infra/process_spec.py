from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessSpec:
    name: str
    enabled: bool = True
