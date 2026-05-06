from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.governance.canonical_governance_evidence import governance_evidence_roundtrip

CANON_EVIDENCE_ROUNDTRIP = True

@dataclass(frozen=True)
class EvidenceRoundtripVerifier:
    def verify(self, *, memory_summary: dict[str, Any], governance_payload: dict[str, Any]) -> dict[str, Any]:
        return governance_evidence_roundtrip(
            expected_memory_summary=memory_summary,
            governance_payload=governance_payload,
        )

__all__ = ['CANON_EVIDENCE_ROUNDTRIP', 'EvidenceRoundtripVerifier']
