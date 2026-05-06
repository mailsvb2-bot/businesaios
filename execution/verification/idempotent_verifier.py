from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Iterable
from execution.verification.evidence_types import EvidenceItem
from execution.verification.verification_contract import VerificationDecision, VerificationRequest
CANON_IDEMPOTENT_VERIFIER = True
def _fingerprint(request: VerificationRequest, evidence: Iterable[EvidenceItem]) -> str:
    ordered = sorted(
        (
            item.evidence_id,
            item.kind,
            item.status,
            item.source,
            ",".join(sorted(item.external_refs)),
            f"{float(item.confidence):.6f}",
        )
        for item in evidence
    )
    raw = "|".join([request.action_id, request.action_type, request.external_confirmation_mode, repr(ordered)])
    return sha256(raw.encode("utf-8")).hexdigest()
@dataclass(slots=True)
class IdempotentVerificationCache:
    _entries: dict[str, VerificationDecision] = field(default_factory=dict)
    def get(self, fingerprint: str) -> VerificationDecision | None:
        return self._entries.get(fingerprint)
    def put(self, fingerprint: str, decision: VerificationDecision) -> None:
        self._entries[fingerprint] = decision
class IdempotentVerifier:
    def __init__(self, *, cache: IdempotentVerificationCache | None = None) -> None:
        self._cache = cache or IdempotentVerificationCache()
    def fingerprint(self, *, request: VerificationRequest, evidence: Iterable[EvidenceItem]) -> str:
        return _fingerprint(request, evidence)
    def get_cached(self, *, request: VerificationRequest, evidence: Iterable[EvidenceItem]) -> tuple[str, VerificationDecision | None]:
        fingerprint = self.fingerprint(request=request, evidence=evidence)
        return fingerprint, self._cache.get(fingerprint)
    def remember(self, *, request: VerificationRequest, evidence: Iterable[EvidenceItem], decision: VerificationDecision) -> str:
        fingerprint = self.fingerprint(request=request, evidence=evidence)
        self._cache.put(fingerprint, decision)
        return fingerprint
__all__ = ["CANON_IDEMPOTENT_VERIFIER", "IdempotentVerificationCache", "IdempotentVerifier"]
