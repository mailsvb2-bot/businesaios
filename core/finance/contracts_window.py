from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FinanceWindow:
    start_at: datetime
    end_at: datetime

    def validate(self) -> None:
        if self.end_at < self.start_at:
            raise ValueError("window end_at must be >= start_at")
