from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FinanceJobSpec:
    job_name: str
    purpose: str
    runtime_phase: str
