from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class SupportsRuntimeBootReport(Protocol):
    report: object


@dataclass(frozen=True)
class AppBootResult:
    runtime: SupportsRuntimeBootReport
    decision_application: object
    startup_report: tuple[str, ...]
