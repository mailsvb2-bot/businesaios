from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class Result:
    ok: bool
    code: str
    message: str = ''
    payload: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @classmethod
    def success(cls, code: str = 'ok', message: str = '', **payload: Any) -> 'Result':
        return cls(ok=True, code=code, message=message, payload=dict(payload))

    @classmethod
    def failure(cls, code: str, message: str, *errors: str, **payload: Any) -> 'Result':
        return cls(ok=False, code=code, message=message, payload=dict(payload), errors=list(errors))
