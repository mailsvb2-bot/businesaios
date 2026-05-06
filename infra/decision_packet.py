from __future__ import annotations

from dataclasses import dataclass, field

from infra.approval_evidence_links import ApprovalEvidenceLink
from infra.constitutional_evidence import ConstitutionalEvidence
from infra.policy_snapshot_evidence import PolicySnapshotEvidence


@dataclass(frozen=True)
class DecisionPacket:
    packet_id: str
    decision_name: str
    actor: str
    policy_version_id: str | None = None
    approval: ApprovalEvidenceLink | None = None
    policy_snapshot: PolicySnapshotEvidence | None = None
    constitutional: ConstitutionalEvidence | None = None
    metadata: dict = field(default_factory=dict)
