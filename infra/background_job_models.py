from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackgroundJobSpec:
    name: str
    enabled: bool = True
