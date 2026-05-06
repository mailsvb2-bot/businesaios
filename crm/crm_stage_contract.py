from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrmStage:
    stage_key: str
    display_name: str
    order_index: int
    is_closed: bool = False
    is_won: bool = False
