from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Customer:
    customer_id: str = ''
    first_seen_at: object | None = None
    segment: str = ''
