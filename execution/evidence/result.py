from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CANON_EVIDENCE_RESULT = True


@dataclass(frozen=True)
class EvidenceResult:
    verified: bool
    status: str
    confidence: float
    external_refs: tuple[str, ...] = ()
    code: str = "unverified"
    message: str = "evidence verification not satisfied"
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verified": bool(self.verified),
            "status": str(self.status),
            "confidence": float(self.confidence),
            "external_refs": list(self.external_refs),
            "code": str(self.code),
            "message": str(self.message),
            "payload": dict(self.payload or {}),
        }


__all__ = ["CANON_EVIDENCE_RESULT", "EvidenceResult"]
