from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DashboardKPIState:
    traces_total: int = 0
    traces_with_success: int = 0
    traces_all_failed: int = 0
    traces_with_blocked: int = 0
    attempts_total: int = 0
