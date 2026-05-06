from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonFsFinding:
    path: str
    kind: str
    message: str
