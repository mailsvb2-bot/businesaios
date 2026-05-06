from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping

from application.effects.effect_outcome_vocabulary import normalize_outcome_status


CANON_EFFECT_EVIDENCE = True


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _normalize_status(value: object, *, default: str = "unknown") -> str:
    return normalize_outcome_status(value, default=default)


def _normalize_evidence_type(value: object) -> str:
    text = _text(value)
    return text or "unknown_evidence"


def _tuple_refs(*parts: object) -> tuple[str, ...]:
    refs: list[str] = []
    for part in parts:
        if isinstance(part, str):
            text = _text(part)
            if text:
                refs.append(text)
        elif isinstance(part, (list, tuple, set)):
            for item in part:
                text = _text(item)
                if text:
                    refs.append(text)
    seen: set[str] = set()
    ordered: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            ordered.append(ref)
    return tuple(ordered)


@dataclass(frozen=True, slots=True)
class EffectEvidenceRecord:
    source: str
    evidence_type: str
    status: str
    summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    external_refs: tuple[str, ...] = ()
    confidence: float = 0.0
    observed_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "evidence_type": self.evidence_type,
            "status": self.status,
            "summary": self.summary,
            "payload": dict(self.payload),
            "external_refs": list(self.external_refs),
            "confidence": float(self.confidence),
            "observed_at": self.observed_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class EffectEvidenceBundle:
    action_type: str
    action_id: str = ""
    records: tuple[EffectEvidenceRecord, ...] = ()

    def external_refs(self) -> tuple[str, ...]:
        refs: list[str] = []
        for record in self.records:
            refs.extend(record.external_refs)
        return _tuple_refs(refs)

    def max_confidence(self) -> float:
        if not self.records:
            return 0.0
        return max(float(record.confidence) for record in self.records)

    def has_external_evidence(self) -> bool:
        return any(record.evidence_type in {"connector_snapshot", "router_result"} for record in self.records)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "action_id": self.action_id,
            "records": [record.to_dict() for record in self.records],
            "external_refs": list(self.external_refs()),
            "max_confidence": self.max_confidence(),
            "has_external_evidence": self.has_external_evidence(),
        }


class EffectEvidenceBuilder:
    def __init__(self, *, action_type: str, action_id: str = "") -> None:
        self._action_type = _text(action_type)
        self._action_id = _text(action_id)
        self._records: list[EffectEvidenceRecord] = []

    def add_record(
        self,
        *,
        source: str,
        evidence_type: str,
        status: str,
        summary: str = "",
        payload: Mapping[str, Any] | None = None,
        external_refs: tuple[str, ...] | list[str] | None = None,
        confidence: float = 0.0,
        observed_at: datetime | None = None,
    ) -> "EffectEvidenceBuilder":
        row_payload = _safe_dict(payload)
        refs = _tuple_refs(external_refs or (), row_payload.get("external_ref"), row_payload.get("external_refs"))
        self._records.append(
            EffectEvidenceRecord(
                source=_text(source),
                evidence_type=_normalize_evidence_type(evidence_type),
                status=_normalize_status(status),
                summary=_text(summary),
                payload=row_payload,
                external_refs=refs,
                confidence=max(0.0, min(1.0, _safe_float(confidence))),
                observed_at=observed_at or _utc_now(),
            )
        )
        return self

    def add_execution_receipt(self, *, payload: Mapping[str, Any] | None = None) -> "EffectEvidenceBuilder":
        row_payload = _safe_dict(payload)
        return self.add_record(
            source="executor",
            evidence_type="execution_receipt",
            status=_text(row_payload.get("status")) or ("executed" if row_payload.get("ok") else "failed"),
            summary=_text(row_payload.get("summary") or row_payload.get("message") or row_payload.get("error")),
            payload=row_payload,
            confidence=1.0 if row_payload.get("ok") else 0.25,
        )

    def add_feedback_evidence(self, *, feedback: Mapping[str, Any] | None = None) -> "EffectEvidenceBuilder":
        payload = _safe_dict(feedback)
        evidence = _safe_dict(payload.get("evidence"))
        evidence_result = _safe_dict(evidence.get("router_result") or evidence)
        if evidence_result:
            self.add_record(
                source="feedback",
                evidence_type="router_result",
                status=_text(payload.get("verification_status") or evidence_result.get("status") or evidence_result.get("code")),
                summary=_text(evidence_result.get("message") or payload.get("reason") or payload.get("error")),
                payload=evidence_result,
                external_refs=evidence_result.get("external_refs") or payload.get("external_refs"),
                confidence=_safe_float(payload.get("verification_confidence") or evidence_result.get("confidence"), default=0.0),
            )
        return self

    def add_router_evidence(self, *, payload: Mapping[str, Any] | None = None) -> "EffectEvidenceBuilder":
        row_payload = _safe_dict(payload)
        if not row_payload:
            return self
        return self.add_record(
            source="evidence_router",
            evidence_type="router_result",
            status=_text(row_payload.get("status") or row_payload.get("code")),
            summary=_text(row_payload.get("message")),
            payload=row_payload,
            external_refs=row_payload.get("external_refs"),
            confidence=_safe_float(row_payload.get("confidence"), default=0.0),
        )

    def add_connector_snapshot(self, *, source: str, payload: Mapping[str, Any] | None = None) -> "EffectEvidenceBuilder":
        row_payload = _safe_dict(payload)
        if not row_payload:
            return self
        return self.add_record(
            source=source,
            evidence_type="connector_snapshot",
            status=_text(row_payload.get("status") or row_payload.get("code")),
            summary=_text(row_payload.get("message") or row_payload.get("summary")),
            payload=row_payload,
            external_refs=row_payload.get("external_refs") or row_payload.get("external_ref"),
            confidence=_safe_float(row_payload.get("confidence"), default=0.0),
        )

    def build(self) -> EffectEvidenceBundle:
        return EffectEvidenceBundle(action_type=self._action_type, action_id=self._action_id, records=tuple(self._records))


__all__ = [
    "CANON_EFFECT_EVIDENCE",
    "EffectEvidenceRecord",
    "EffectEvidenceBundle",
    "EffectEvidenceBuilder",
]
