from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.action_catalog import get_action_spec, known_action_types

CANON_ACTION_CAPABILITY_MATRIX = True


@dataclass(frozen=True)
class ActionCapability:
    action_type: str
    action_class: str
    decisionable: bool
    routable: bool
    executable: bool
    externally_verified: bool
    idempotent: bool
    reversible: bool
    approval_required: bool
    bounded_by_blast_radius: bool
    prod_ready: bool
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


def get_action_capability(action_type: str) -> ActionCapability:
    spec = get_action_spec(action_type)
    return ActionCapability(
        action_type=spec.action_type,
        action_class=spec.action_class,
        decisionable=spec.decisionable,
        routable=spec.routable,
        executable=spec.executable,
        externally_verified=spec.externally_verified,
        idempotent=spec.idempotent,
        reversible=spec.reversible,
        approval_required=spec.approval_required,
        bounded_by_blast_radius=spec.bounded_by_blast_radius,
        prod_ready=spec.prod_ready,
        notes=tuple(spec.notes),
    )


def build_action_capability_matrix() -> tuple[ActionCapability, ...]:
    return tuple(get_action_capability(action_type) for action_type in known_action_types())


def build_action_capability_matrix_payload() -> list[dict[str, Any]]:
    return [entry.as_dict() for entry in build_action_capability_matrix()]


__all__ = [
    'CANON_ACTION_CAPABILITY_MATRIX',
    'ActionCapability',
    'build_action_capability_matrix',
    'build_action_capability_matrix_payload',
    'get_action_capability',
]
