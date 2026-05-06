from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CustomerSignal:
    signal_id: str = ''
    customer_id: str = ''
    intent_score: str = ''
