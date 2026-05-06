from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SaveCommand:
    tenant_id: str
    payload: dict[str, Any]
