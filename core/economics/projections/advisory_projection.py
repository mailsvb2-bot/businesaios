from __future__ import annotations

from dataclasses import dataclass

from ..types import EconomicsSnapshot


@dataclass
class AdvisoryProjection:
    def project(self, snapshot: EconomicsSnapshot) -> dict:
        return {
            "snapshot_id": snapshot.snapshot_id.value,
            "policy_advice": snapshot.policy_advice,
            "advisory_only": snapshot.metadata.get("advisory_only", False),
            "decision_boundary": snapshot.metadata.get("decision_boundary"),
        }
