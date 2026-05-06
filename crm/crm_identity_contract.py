from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmIdentity:
    canonical_key: str
    email: str | None = None
    phone: str | None = None
    external_ids: Mapping[str, str] = field(default_factory=dict)
