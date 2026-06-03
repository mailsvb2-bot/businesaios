from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from execution.effect_evidence import EffectEvidenceBundle
from application.effects.effect_outcome_vocabulary import normalize_outcome_status, outcome_is_verified


CANON_OUTCOME_VERIFIER = True


_SUCCESS_STATUSES = {"verified"}
_EXTERNAL_EVIDENCE_TYPES = {"connector_snapshot", "router_result"}
_EXTERNAL_CONFIRMATION_MODES = {"auto", "required", "not_required"}


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _normalize_confirmation_mode(value: object) -> str:
    text = _text(value)
    return text if text in _EXTERNAL_CONFIRMATION_MODES else "auto"


@dataclass(frozen=True, slots=True)
class OutcomeExpectation:
    action_type: str
    required_evidence_types: tuple[str, ...] = ()
    required_sources: tuple[str, ...] = ()
    required_statuses: tuple[str, ...] = tuple(sorted(_SUCCESS_STATUSES))
    min_successful_records: int = 1
    external_confirmation_mode: str = "required"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "required_evidence_types": list(self.required_evidence_types),
            "required_sources": list(self.required_sources),
            "required_statuses": list(self.required_statuses),
            "min_successful_records": self.min_successful_records,
            "external_confirmation_mode": self.external_confirmation_mode,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class OutcomeVerificationResult:
    action_type: str
    action_id: str
    verified: bool
    verification_status: str
    reason: str
    matched_records: int
    external_matched_records: int
    total_records: int
    evidence: dict[str, Any]
    expectation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "action_id": self.action_id,
            "verified": self.verified,
            "verification_status": self.verification_status,
            "reason": self.reason,
            "matched_records": self.matched_records,
            "external_matched_records": self.external_matched_records,
            "total_records": self.total_records,
            "evidence": dict(self.evidence),
            "expectation": dict(self.expectation),
        }


class OutcomeVerifier:
    def verify(self, *, expectation: OutcomeExpectation, evidence: EffectEvidenceBundle) -> OutcomeVerificationResult:
        total = len(evidence.records)
        required_types = set(expectation.required_evidence_types)
        required_sources = set(expectation.required_sources)
        required_statuses = {_text(status).casefold() for status in expectation.required_statuses if _text(status)}
        matched = 0
        external_matched = 0
        for record in evidence.records:
            if required_types and record.evidence_type not in required_types:
                continue
            if required_sources and record.source not in required_sources:
                continue
            if required_statuses and normalize_outcome_status(record.status, default=_text(record.status).casefold()) not in required_statuses:
                continue
            matched += 1
            if record.evidence_type in _EXTERNAL_EVIDENCE_TYPES:
                external_matched += 1

        enough_matches = matched >= max(1, int(expectation.min_successful_records))
        confirmation_mode = _normalize_confirmation_mode(expectation.external_confirmation_mode)
        if not enough_matches:
            status = normalize_outcome_status("unverified", verified=False)
            reason = "insufficient_observed_effect"
            verified = outcome_is_verified(status, verified=False)
        elif confirmation_mode == "required" and external_matched < 1:
            status = normalize_outcome_status("missing_external_confirmation", verified=False)
            reason = "missing_external_confirmation"
            verified = outcome_is_verified(status, verified=False)
        else:
            status = normalize_outcome_status("verified", verified=True)
            reason = "observable_expectation_satisfied"
            verified = outcome_is_verified(status, verified=True)

        return OutcomeVerificationResult(
            action_type=expectation.action_type,
            action_id=evidence.action_id,
            verified=verified,
            verification_status=status,
            reason=reason,
            matched_records=matched,
            external_matched_records=external_matched,
            total_records=total,
            evidence=evidence.to_dict(),
            expectation=expectation.to_dict(),
        )


def expectation_from_action(action_type: str, *, external_confirmation_mode: str = "required") -> OutcomeExpectation:
    action_text = _text(action_type)
    required_types: tuple[str, ...]
    if any(token in action_text for token in ("publish", "launch", "update", "send", "route", "create", "write")):
        required_types = ("execution_receipt", "connector_snapshot", "router_result")
    else:
        required_types = ("execution_receipt", "router_result")
    return OutcomeExpectation(
        action_type=action_text,
        required_evidence_types=required_types,
        external_confirmation_mode=_normalize_confirmation_mode(external_confirmation_mode),
    )


__all__ = [
    "CANON_OUTCOME_VERIFIER",
    "OutcomeExpectation",
    "OutcomeVerificationResult",
    "OutcomeVerifier",
    "expectation_from_action",
]
