from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANON_EXECUTION_ACTION_CONTRACTS = True


@dataclass(frozen=True)
class ActionSpec:
    action_type: str
    action_class: str
    decisionable: bool = True
    routable: bool = True
    executable: bool = True
    externally_verified: bool = False
    idempotent: bool = False
    reversible: bool = False
    approval_required: bool = False
    bounded_by_blast_radius: bool = False
    prod_ready: bool = False
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            'action_type': self.action_type,
            'action_class': self.action_class,
            'decisionable': self.decisionable,
            'routable': self.routable,
            'executable': self.executable,
            'externally_verified': self.externally_verified,
            'idempotent': self.idempotent,
            'reversible': self.reversible,
            'approval_required': self.approval_required,
            'bounded_by_blast_radius': self.bounded_by_blast_radius,
            'prod_ready': self.prod_ready,
            'notes': list(self.notes),
        }


__all__ = ["ActionSpec", "CANON_EXECUTION_ACTION_CONTRACTS"]
