from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from collections.abc import Mapping
from execution.verification.evidence_types import EvidenceItem, normalize_evidence_kind, normalize_evidence_status
CANON_VERIFICATION_CONTRACT = True

def _utc_now() -> datetime:
    return datetime.now(UTC)

def _text(value: object) -> str:
    return str(value or "").strip()

def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}

def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)

def _safe_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _text(value).casefold()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)

def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None

def _safe_backoff_sequence(value: object) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)):
        return (30, 120, 300)
    result: list[int] = []
    for item in value:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number > 0:
            result.append(number)
    return tuple(result) or (30, 120, 300)

@dataclass(frozen=True, slots=True)
class VerificationRequest:
    action_id: str
    action_type: str
    tenant_id: str = ""
    business_id: str = ""
    run_id: str = ""
    step_index: int = 0
    external_confirmation_mode: str = "required"
    evidence: tuple[EvidenceItem, ...] = ()
    requested_at: datetime = field(default_factory=_utc_now)
    verification_deadline: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        *,
        action: Mapping[str, Any],
        evidence: tuple[EvidenceItem, ...] | list[EvidenceItem] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "VerificationRequest":
        payload = _safe_dict(action)
        requested_at = _parse_datetime(payload.get("requested_at") or payload.get("observed_at")) or _utc_now()
        deadline_raw = payload.get("verification_deadline")
        deadline = _parse_datetime(deadline_raw)
        return cls(
            action_id=_text(payload.get("action_id")),
            action_type=_text(payload.get("action_type")),
            tenant_id=_text(payload.get("tenant_id")),
            business_id=_text(payload.get("business_id")),
            run_id=_text(payload.get("run_id")),
            step_index=_safe_int(payload.get("step_index"), default=0),
            external_confirmation_mode=_text(payload.get("external_confirmation_mode") or "required"),
            evidence=tuple(evidence or ()),
            requested_at=requested_at,
            verification_deadline=deadline,
            metadata={**payload, **_safe_dict(metadata)},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "run_id": self.run_id,
            "step_index": self.step_index,
            "external_confirmation_mode": self.external_confirmation_mode,
            "requested_at": self.requested_at.isoformat(),
            "verification_deadline": None if self.verification_deadline is None else self.verification_deadline.isoformat(),
            "metadata": dict(self.metadata),
            "evidence": [item.to_dict() for item in self.evidence],
        }

@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    min_evidence_count: int = 1
    require_external_evidence: bool = True
    require_authoritative_source: bool = False
    allow_delayed_verification: bool = True
    conflict_is_terminal: bool = True
    timeout_seconds: int = 900
    retry_backoff_seconds: tuple[int, ...] = (30, 120, 300)
    positive_confidence_threshold: float = 0.0
    authoritative_sources: tuple[str, ...] = (
        "connector",
        "platform",
        "crm",
        "payment_gateway",
        "website",
        "effect_router",
        "callback",
        "ledger",
    )
    def to_dict(self) -> dict[str, Any]:
        return {
            "min_evidence_count": self.min_evidence_count,
            "require_external_evidence": self.require_external_evidence,
            "require_authoritative_source": self.require_authoritative_source,
            "allow_delayed_verification": self.allow_delayed_verification,
            "conflict_is_terminal": self.conflict_is_terminal,
            "timeout_seconds": self.timeout_seconds,
            "retry_backoff_seconds": list(self.retry_backoff_seconds),
            "positive_confidence_threshold": self.positive_confidence_threshold,
            "authoritative_sources": list(self.authoritative_sources),
        }
    def verification_deadline_for(self, requested_at: datetime | None = None) -> datetime:
        base = requested_at or _utc_now()
        return base + timedelta(seconds=max(1, int(self.timeout_seconds)))

@dataclass(frozen=True, slots=True)
class VerificationDecision:
    action_id: str
    action_type: str
    verified: bool
    status: str
    code: str
    reason: str
    source_of_truth: str
    confidence: float
    observed_external_refs: tuple[str, ...] = ()
    matched_evidence_ids: tuple[str, ...] = ()
    conflicting_evidence_ids: tuple[str, ...] = ()
    pending_evidence_ids: tuple[str, ...] = ()
    retryable: bool = False
    delayed: bool = False
    timed_out: bool = False
    decision_fingerprint: str = ""
    decided_at: datetime = field(default_factory=_utc_now)
    policy_snapshot: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "verified": self.verified,
            "status": self.status,
            "code": self.code,
            "reason": self.reason,
            "source_of_truth": self.source_of_truth,
            "confidence": float(self.confidence),
            "observed_external_refs": list(self.observed_external_refs),
            "matched_evidence_ids": list(self.matched_evidence_ids),
            "conflicting_evidence_ids": list(self.conflicting_evidence_ids),
            "pending_evidence_ids": list(self.pending_evidence_ids),
            "retryable": self.retryable,
            "delayed": self.delayed,
            "timed_out": self.timed_out,
            "decision_fingerprint": self.decision_fingerprint,
            "decided_at": self.decided_at.isoformat(),
            "policy_snapshot": dict(self.policy_snapshot),
            "summary": dict(self.summary),
        }

def verification_policy_from_action(action: Mapping[str, Any] | None) -> VerificationPolicy:
    payload = _safe_dict(action)
    mode = _text(payload.get("external_confirmation_mode") or "required").casefold()
    category = _text(
        payload.get("action_category")
        or payload.get("effect_category")
        or payload.get("execution_category")
        or payload.get("kind")
    ).casefold()
    not_required = category in {
        "read_only",
        "readonly",
        "read-only",
        "advisory",
        "bookkeeping",
        "internal_bookkeeping",
        "noop",
        "no_op",
        "no-op",
    } or mode == "not_required"
    return VerificationPolicy(
        min_evidence_count=0 if not_required else max(1, _safe_int(payload.get("min_evidence_count"), default=1)),
        require_external_evidence=not not_required,
        require_authoritative_source=_safe_bool(payload.get("require_authoritative_source"), default=False),
        allow_delayed_verification=_safe_bool(payload.get("allow_delayed_verification"), default=True),
        conflict_is_terminal=_safe_bool(payload.get("conflict_is_terminal"), default=True),
        timeout_seconds=max(1, _safe_int(payload.get("verification_timeout_seconds"), default=900)),
        retry_backoff_seconds=_safe_backoff_sequence(payload.get("verification_retry_backoff_seconds")),
        positive_confidence_threshold=max(0.0, min(1.0, _safe_float(payload.get("positive_confidence_threshold"), default=0.0))),
    )

def evidence_item_from_mapping(item: Mapping[str, Any]) -> EvidenceItem:
    payload = _safe_dict(item)
    refs = payload.get("external_refs")
    if not isinstance(refs, (list, tuple, set)):
        refs = [refs] if _text(refs) else []
    return EvidenceItem(
        evidence_id=_text(payload.get("evidence_id")),
        action_id=_text(payload.get("action_id")),
        action_type=_text(payload.get("action_type")),
        source=_text(payload.get("source")),
        kind=normalize_evidence_kind(payload.get("kind") or payload.get("evidence_type")),
        status=normalize_evidence_status(payload.get("status")),
        external_refs=tuple(str(ref).strip() for ref in refs if str(ref).strip()),
        confidence=_safe_float(payload.get("confidence"), default=0.0),
        payload=_safe_dict(payload.get("payload")),
        observed_at=payload.get("observed_at"),
        metadata=_safe_dict(payload.get("metadata")),
    )
__all__ = [
    "CANON_VERIFICATION_CONTRACT",
    "VerificationRequest",
    "VerificationPolicy",
    "VerificationDecision",
    "verification_policy_from_action",
    "evidence_item_from_mapping",
]
