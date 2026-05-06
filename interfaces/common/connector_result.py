from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class ConnectorResult:
    ok: bool
    code: str
    message: str = ''
    payload: Dict[str, Any] = field(default_factory=dict)
