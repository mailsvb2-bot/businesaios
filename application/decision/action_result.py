from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANON_CORE_DECISION_ACTION_RESULT = True


@dataclass(frozen=True)
class ActionExecutionResult:
    status: str
    action_type: str
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


__all__ = ["ActionExecutionResult", "CANON_CORE_DECISION_ACTION_RESULT"]
