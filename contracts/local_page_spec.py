from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LocalPageSpec:
    spec_id: str = ''
    city: str = ''
    service: str = ''
