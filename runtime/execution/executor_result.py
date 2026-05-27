from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    output: Any = None
    error: Optional[str] = None
    decision_id: Optional[str] = None
    correlation_id: Optional[str] = None
