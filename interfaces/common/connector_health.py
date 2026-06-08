from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConnectorHealth:
    connector_name: str
    healthy: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
