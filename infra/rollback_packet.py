from __future__ import annotations

from dataclasses import dataclass, field

from infra.constitutional_evidence import ConstitutionalEvidence
from infra.policy_snapshot_evidence import PolicySnapshotEvidence


@dataclass(frozen=True)
class RollbackPacket:
    packet_id: str
    rollback_id: str
    actor: str
    target_name: str
    reason: str
    policy_version_id: str | None = None
    policy_snapshot: PolicySnapshotEvidence | None = None
    constitutional: ConstitutionalEvidence | None = None
    metadata: dict = field(default_factory=dict)
