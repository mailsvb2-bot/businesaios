from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AllocationConstraints:
    min_cash_buffer: Decimal = Decimal('0')
    max_channel_share: Decimal = Decimal('1')
    max_entity_share: Decimal = Decimal('1')
