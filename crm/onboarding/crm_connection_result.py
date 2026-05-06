from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from crm.crm_connection_contract import CrmConnectionRef


@dataclass(frozen=True)
class CrmConnectionResult:
    success: bool
    connection: CrmConnectionRef | None
    reason: str
    diagnostics: Mapping[str, object] = field(default_factory=dict)
