from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    output: Any = None
    error: str | None = None
    decision_id: str | None = None
    correlation_id: str | None = None
