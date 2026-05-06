from __future__ import annotations

from dataclasses import dataclass

from infra.governance_evidence_service import GovernanceEvidenceService
from infra.operator_session_records import OperatorSessionRegistry


@dataclass(frozen=True)
class GovernanceEvidenceBootResult:
    sessions: OperatorSessionRegistry
    service: GovernanceEvidenceService
