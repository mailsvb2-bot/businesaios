from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANON_BUSINESS_MEMORY_TAXONOMY = True

def _text(value: object) -> str:
    return str(value or "").strip()

def _norm(value: object) -> str:
    return _text(value).casefold().replace("-", "_").replace(" ", "_")

@dataclass(frozen=True)
class NormalizedFeedback:
    failure_kind: str | None
    outcome_kinds: tuple[str, ...]
    evidence_labels: tuple[str, ...]
    raw_error: str
    raw_stop_reason: str

@dataclass(frozen=True)
class BusinessMemoryTaxonomy:
    def normalize_feedback(self, *, completed: bool, stop_reason: str, final_feedback: dict[str, Any]) -> NormalizedFeedback:
        raw_error = _text(dict(final_feedback or {}).get("error"))
        raw_stop_reason = _text(stop_reason)
        failure_kind = None if completed else self._normalize_failure_kind(error=raw_error, stop_reason=raw_stop_reason)
        outcome_kinds = self._normalize_outcome_kinds(completed=completed, final_feedback=dict(final_feedback or {}))
        labels: list[str] = []
        if failure_kind:
            labels.append(f"failure:{failure_kind}")
        for outcome in outcome_kinds:
            labels.append(f"outcome:{outcome}")
        return NormalizedFeedback(failure_kind=failure_kind, outcome_kinds=outcome_kinds, evidence_labels=tuple(dict.fromkeys(labels)), raw_error=raw_error, raw_stop_reason=raw_stop_reason)
    def _normalize_failure_kind(self, *, error: str, stop_reason: str) -> str:
        joined = f"{_norm(error)}|{_norm(stop_reason)}"
        if "timeout" in joined:
            return "timeout_external"
        if "rate_limit" in joined or "ratelimit" in joined:
            return "rate_limit"
        if "auth" in joined or "unauthorized" in joined or "forbidden" in joined:
            return "auth_failure"
        if "network" in joined or "connection" in joined or "dns" in joined:
            return "network_failure"
        if "validation" in joined or "invalid" in joined:
            return "validation_failure"
        if "operator" in joined or "manual_review" in joined or "human" in joined:
            return "operator_handoff_required"
        if "budget" in joined or "spend" in joined or "funds" in joined:
            return "budget_constraint"
        if "policy" in joined or "guard" in joined or "unsafe" in joined:
            return "policy_block"
        stable_stop = _norm(stop_reason)
        if stable_stop:
            return f"stop_reason:{stable_stop}"
        stable_error = _norm(error)
        if stable_error:
            return f"error:{stable_error}"
        return "execution_failed_unknown"
    def _normalize_outcome_kinds(self, *, completed: bool, final_feedback: dict[str, Any]) -> tuple[str, ...]:
        outcomes: list[str] = []
        if completed and bool(dict(final_feedback or {}).get("goal_reached")):
            outcomes.append("goal_reached")
        normalized_outcome = dict(dict(final_feedback or {}).get("normalized_outcome") or {})
        for key, value in normalized_outcome.items():
            stable_key = _norm(key)
            stable_value = _norm(value)
            if stable_key and stable_value:
                outcomes.append(f"{stable_key}={stable_value}")
            elif stable_key:
                outcomes.append(stable_key)
        return tuple(dict.fromkeys(outcomes))
__all__ = ["BusinessMemoryTaxonomy", "CANON_BUSINESS_MEMORY_TAXONOMY", "NormalizedFeedback"]
