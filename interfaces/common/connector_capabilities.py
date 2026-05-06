from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConnectorCapabilities:
    read: bool = True
    write: bool = False
    verify: bool = False
    dry_run: bool = False
    idempotent: bool = False
    reversible: bool = False
    requires_human_approval: bool = True
    evidence_fields: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "read": bool(self.read),
            "write": bool(self.write),
            "verify": bool(self.verify),
            "dry_run": bool(self.dry_run),
            "idempotent": bool(self.idempotent),
            "reversible": bool(self.reversible),
            "requires_human_approval": bool(self.requires_human_approval),
            "evidence_fields": list(self.evidence_fields),
            "metadata": dict(self.metadata),
        }


__all__ = ["ConnectorCapabilities"]
