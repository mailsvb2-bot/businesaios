from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrmOwner:
    owner_id: str
    display_name: str
    email: str | None = None
