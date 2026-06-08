from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConnectorResult:
    ok: bool
    code: str
    message: str = ''
    payload: dict[str, Any] = field(default_factory=dict)
