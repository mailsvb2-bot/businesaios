from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from collections.abc import Mapping
CANON_VERIFICATION_EVIDENCE_TYPES = True
EVIDENCE_KIND_EXECUTION_RECEIPT = "execution_receipt"
EVIDENCE_KIND_ROUTER_RESULT = "router_result"
EVIDENCE_KIND_CONNECTOR_SNAPSHOT = "connector_snapshot"
EVIDENCE_KIND_CALLBACK = "callback"
EVIDENCE_KIND_LEDGER_ENTRY = "ledger_entry"
EVIDENCE_KIND_OPERATOR_CONFIRMATION = "operator_confirmation"
EVIDENCE_KIND_UNKNOWN = "unknown"
EVIDENCE_STATUS_VERIFIED = "verified"
EVIDENCE_STATUS_OBSERVED = "observed"
EVIDENCE_STATUS_PENDING = "pending"
EVIDENCE_STATUS_FAILED = "failed"
EVIDENCE_STATUS_CONFLICTING = "conflicting"
EVIDENCE_STATUS_MISSING = "missing"
EVIDENCE_STATUS_UNKNOWN = "unknown"
_KIND_ALIASES = {
    "receipt": EVIDENCE_KIND_EXECUTION_RECEIPT,
    "execution": EVIDENCE_KIND_EXECUTION_RECEIPT,
    "execution_receipt": EVIDENCE_KIND_EXECUTION_RECEIPT,
    "router": EVIDENCE_KIND_ROUTER_RESULT,
    "router_result": EVIDENCE_KIND_ROUTER_RESULT,
    "connector": EVIDENCE_KIND_CONNECTOR_SNAPSHOT,
    "connector_snapshot": EVIDENCE_KIND_CONNECTOR_SNAPSHOT,
    "callback": EVIDENCE_KIND_CALLBACK,
    "webhook": EVIDENCE_KIND_CALLBACK,
    "ledger": EVIDENCE_KIND_LEDGER_ENTRY,
    "ledger_entry": EVIDENCE_KIND_LEDGER_ENTRY,
    "operator_confirmation": EVIDENCE_KIND_OPERATOR_CONFIRMATION,
}
_STATUS_ALIASES = {
    "success": EVIDENCE_STATUS_VERIFIED,
    "ok": EVIDENCE_STATUS_VERIFIED,
    "accepted": EVIDENCE_STATUS_VERIFIED,
    "verified": EVIDENCE_STATUS_VERIFIED,
    "observed": EVIDENCE_STATUS_OBSERVED,
    "executed": EVIDENCE_STATUS_OBSERVED,
    "pending": EVIDENCE_STATUS_PENDING,
    "queued": EVIDENCE_STATUS_PENDING,
    "retrying": EVIDENCE_STATUS_PENDING,
    "retryable": EVIDENCE_STATUS_PENDING,
    "failed": EVIDENCE_STATUS_FAILED,
    "error": EVIDENCE_STATUS_FAILED,
    "unverified": EVIDENCE_STATUS_FAILED,
    "conflicting": EVIDENCE_STATUS_CONFLICTING,
    "mismatch": EVIDENCE_STATUS_CONFLICTING,
    "missing": EVIDENCE_STATUS_MISSING,
    "unknown": EVIDENCE_STATUS_UNKNOWN,
}
_AUTHORITATIVE_KINDS = (
    EVIDENCE_KIND_CONNECTOR_SNAPSHOT,
    EVIDENCE_KIND_CALLBACK,
    EVIDENCE_KIND_LEDGER_ENTRY,
    EVIDENCE_KIND_ROUTER_RESULT,
)
def _utc_now() -> datetime:
    return datetime.now(UTC)
def _text(value: object) -> str:
    return str(value or "").strip()
def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
def _safe_list(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = _text(value)
    return (text,) if text else ()
def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    text = _text(value)
    if not text:
        return _utc_now()
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return _utc_now()
def _payload_digest(payload: Mapping[str, Any] | None) -> str:
    data = _safe_dict(payload)
    if not data:
        return ""
    raw = repr(sorted((str(key), repr(value)) for key, value in data.items()))
    return sha256(raw.encode("utf-8")).hexdigest()[:16]
def normalize_evidence_kind(value: object) -> str:
    text = _text(value).casefold().replace("-", "_").replace(" ", "_")
    return _KIND_ALIASES.get(text, text or EVIDENCE_KIND_UNKNOWN)
def normalize_evidence_status(value: object) -> str:
    text = _text(value).casefold().replace("-", "_").replace(" ", "_")
    return _STATUS_ALIASES.get(text, text or EVIDENCE_STATUS_UNKNOWN)
def evidence_status_is_positive(status: object) -> bool:
    return normalize_evidence_status(status) in {EVIDENCE_STATUS_VERIFIED, EVIDENCE_STATUS_OBSERVED}
def evidence_status_is_negative(status: object) -> bool:
    return normalize_evidence_status(status) in {EVIDENCE_STATUS_FAILED, EVIDENCE_STATUS_CONFLICTING}
def evidence_status_is_pending(status: object) -> bool:
    return normalize_evidence_status(status) == EVIDENCE_STATUS_PENDING
def authoritative_evidence_kinds() -> tuple[str, ...]:
    return _AUTHORITATIVE_KINDS
@dataclass(frozen=True, slots=True)
class EvidenceItem:
    source: str
    kind: str
    status: str
    evidence_id: str = ""
    action_id: str = ""
    action_type: str = ""
    external_refs: tuple[str, ...] = ()
    confidence: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _text(self.source))
        object.__setattr__(self, "kind", normalize_evidence_kind(self.kind))
        object.__setattr__(self, "status", normalize_evidence_status(self.status))
        object.__setattr__(self, "action_id", _text(self.action_id))
        object.__setattr__(self, "action_type", _text(self.action_type))
        object.__setattr__(self, "external_refs", _safe_list(self.external_refs))
        object.__setattr__(self, "payload", _safe_dict(self.payload))
        object.__setattr__(self, "metadata", _safe_dict(self.metadata))
        object.__setattr__(self, "observed_at", _parse_datetime(self.observed_at))
        object.__setattr__(self, "confidence", max(0.0, min(1.0, float(self.confidence or 0.0))))
        object.__setattr__(self, "evidence_id", _text(self.evidence_id) or self.stable_identity())
    def stable_identity(self) -> str:
        raw = "|".join(
            [
                self.action_id,
                self.action_type,
                self.source,
                self.kind,
                self.status,
                ",".join(self.external_refs),
                _payload_digest(self.payload),
                self.observed_at.isoformat(),
            ]
        )
        return sha256(raw.encode("utf-8")).hexdigest()[:24]
    def correlation_key(self) -> str:
        if self.external_refs:
            return f"refs:{'|'.join(sorted(self.external_refs))}"
        if self.action_id:
            return f"action:{self.action_id}"
        return f"evidence:{self.evidence_id}"
    def is_authoritative(self) -> bool:
        return self.kind in _AUTHORITATIVE_KINDS
    def is_positive(self) -> bool:
        return evidence_status_is_positive(self.status)
    def is_negative(self) -> bool:
        return evidence_status_is_negative(self.status)
    def is_pending(self) -> bool:
        return evidence_status_is_pending(self.status)
    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "source": self.source,
            "kind": self.kind,
            "status": self.status,
            "external_refs": list(self.external_refs),
            "confidence": float(self.confidence),
            "payload": dict(self.payload),
            "observed_at": self.observed_at.isoformat(),
            "metadata": dict(self.metadata),
        }
__all__ = [
    "CANON_VERIFICATION_EVIDENCE_TYPES",
    "EvidenceItem",
    "EVIDENCE_KIND_EXECUTION_RECEIPT",
    "EVIDENCE_KIND_ROUTER_RESULT",
    "EVIDENCE_KIND_CONNECTOR_SNAPSHOT",
    "EVIDENCE_KIND_CALLBACK",
    "EVIDENCE_KIND_LEDGER_ENTRY",
    "EVIDENCE_KIND_OPERATOR_CONFIRMATION",
    "EVIDENCE_KIND_UNKNOWN",
    "EVIDENCE_STATUS_VERIFIED",
    "EVIDENCE_STATUS_OBSERVED",
    "EVIDENCE_STATUS_PENDING",
    "EVIDENCE_STATUS_FAILED",
    "EVIDENCE_STATUS_CONFLICTING",
    "EVIDENCE_STATUS_MISSING",
    "EVIDENCE_STATUS_UNKNOWN",
    "normalize_evidence_kind",
    "normalize_evidence_status",
    "evidence_status_is_positive",
    "evidence_status_is_negative",
    "evidence_status_is_pending",
    "authoritative_evidence_kinds",
]
