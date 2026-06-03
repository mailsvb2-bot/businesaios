from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Iterable, Mapping, Sequence

from execution.error_family_classifier import ErrorFamilyClassifier

CANON_FAILURE_PATTERN_DETECTOR = True
FAILURE_PATTERN_SCHEMA_VERSION = 1

_DEFAULT_RECURRING_THRESHOLD = 2
_DEFAULT_HIGH_SEVERITY_THRESHOLD = 4
_DEFAULT_QUARANTINE_THRESHOLD = 5
_MAX_TIMESTAMP_SAMPLES = 12
_MAX_ERROR_SAMPLE_LENGTH = 280


def _text(value: object) -> str:
    return str(value or "").strip()


def _text_lower(value: object) -> str:
    return _text(value).lower()


def _safe_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _text_lower(value) in {"1", "true", "yes", "y", "on"}


def _clamp_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _bounded_error_sample(value: object) -> str:
    token = _text(value)
    if len(token) <= _MAX_ERROR_SAMPLE_LENGTH:
        return token
    return token[: _MAX_ERROR_SAMPLE_LENGTH - 3].rstrip() + "..."


def _dedupe_preserve_order(values: Sequence[str], *, limit: int) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        token = _text(raw)
        if not token:
            continue
        marker = token.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(token)
        if len(result) >= max(1, int(limit)):
            break
    return tuple(result)


def _severity_rank(value: str) -> int:
    return {
        "low": 0,
        "medium": 1,
        "high": 2,
        "critical": 3,
    }.get(_text_lower(value), 0)


@dataclass(frozen=True)
class FailureEvent:
    tenant_id: str = ""
    business_id: str = ""
    action_type: str = ""
    error_family: str = "unknown"
    error_message: str = ""
    capability: str = ""
    service_name: str = ""
    recovery_mode: str = ""
    retry_kind: str = ""
    attempt_index: int = 0
    failed: bool = True
    recovered_after_retry: bool = False
    blocked_by_policy: bool = False
    approval_required: bool = False
    operator_required: bool = False
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FailurePattern:
    schema_version: int = FAILURE_PATTERN_SCHEMA_VERSION
    tenant_id: str = ""
    business_id: str = ""
    action_type: str = ""
    error_family: str = "unknown"
    capability: str = ""
    service_name: str = ""
    total_failures: int = 0
    consecutive_failures: int = 0
    total_events: int = 0
    recovered_after_retry_count: int = 0
    operator_required_count: int = 0
    policy_block_count: int = 0
    max_attempt_index: int = 0
    recurring: bool = False
    severity: str = "low"
    sample_error: str = ""
    timestamps: tuple[str, ...] = field(default_factory=tuple)
    recommended_backoff_floor_seconds: int = 0
    recommended_max_attempts: int = 1
    should_open_operator_handoff: bool = False
    should_quarantine_capability: bool = False
    should_cooldown: bool = False
    evidence_only: bool = True
    must_not_issue_decision: bool = True

    @property
    def success_after_retry_rate(self) -> float:
        if self.total_failures <= 0:
            return 0.0
        return _clamp_unit(self.recovered_after_retry_count / float(self.total_failures))

    @property
    def operator_pressure_rate(self) -> float:
        if self.total_failures <= 0:
            return 0.0
        return _clamp_unit(self.operator_required_count / float(self.total_failures))

    @property
    def policy_block_rate(self) -> float:
        if self.total_failures <= 0:
            return 0.0
        return _clamp_unit(self.policy_block_count / float(self.total_failures))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["success_after_retry_rate"] = self.success_after_retry_rate
        payload["operator_pressure_rate"] = self.operator_pressure_rate
        payload["policy_block_rate"] = self.policy_block_rate
        return payload


@dataclass(frozen=True)
class FailurePatternReport:
    schema_version: int = FAILURE_PATTERN_SCHEMA_VERSION
    tenant_id: str = ""
    business_id: str = ""
    patterns: tuple[FailurePattern, ...] = field(default_factory=tuple)
    total_events: int = 0
    total_failures: int = 0
    recurring_pattern_count: int = 0
    high_severity_pattern_count: int = 0
    evidence_only: bool = True
    must_not_issue_decision: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "tenant_id": str(self.tenant_id),
            "business_id": str(self.business_id),
            "patterns": [item.to_dict() for item in self.patterns],
            "total_events": int(self.total_events),
            "total_failures": int(self.total_failures),
            "recurring_pattern_count": int(self.recurring_pattern_count),
            "high_severity_pattern_count": int(self.high_severity_pattern_count),
            "evidence_only": True,
            "must_not_issue_decision": True,
        }


class FailurePatternDetector:
    """
    Evidence-only detector for recurring retry/failure shapes.

    It must never become a second decision center.
    """

    def __init__(
        self,
        *,
        error_family_classifier: ErrorFamilyClassifier | None = None,
        recurring_threshold: int = _DEFAULT_RECURRING_THRESHOLD,
        high_severity_threshold: int = _DEFAULT_HIGH_SEVERITY_THRESHOLD,
        quarantine_threshold: int = _DEFAULT_QUARANTINE_THRESHOLD,
    ) -> None:
        self._classifier = error_family_classifier or ErrorFamilyClassifier()
        self._recurring_threshold = max(2, int(recurring_threshold))
        self._high_severity_threshold = max(self._recurring_threshold, int(high_severity_threshold))
        self._quarantine_threshold = max(self._high_severity_threshold, int(quarantine_threshold))

    def _normalize_event(self, payload: Mapping[str, Any]) -> FailureEvent:
        body = dict(payload)
        error_message = _text(
            body.get("error_message")
            or body.get("result_error")
            or body.get("error")
            or body.get("reason")
        )
        retry_kind = _text_lower(body.get("retry_kind"))
        error_family = _text_lower(body.get("error_family")) or self._classifier.classify(error_message) or "unknown"
        blocked_by_policy = _safe_bool(body.get("blocked_by_policy"))
        approval_required = _safe_bool(body.get("approval_required"))
        operator_required = _safe_bool(body.get("operator_required")) or approval_required or retry_kind == "operator_required"
        if "failed" in body:
            failed = _safe_bool(body.get("failed"))
        else:
            ok = _safe_bool(body.get("ok")) or _safe_bool(body.get("success"))
            failed = not ok if error_message or retry_kind != "success" else False
        recovered_after_retry = (
            _safe_bool(body.get("recovered_after_retry"))
            or _safe_bool(body.get("success_after_retry"))
            or (retry_kind == "success" and max(0, _safe_int(body.get("attempt_index"))) > 0)
        )
        return FailureEvent(
            tenant_id=_text(body.get("tenant_id")),
            business_id=_text(body.get("business_id")),
            action_type=_text(body.get("action_type") or body.get("action")),
            error_family=error_family or "unknown",
            error_message=error_message,
            capability=_text(body.get("capability") or body.get("capability_key")),
            service_name=_text(body.get("service_name") or body.get("service") or body.get("runner_name")),
            recovery_mode=_text(body.get("recovery_mode")),
            retry_kind=retry_kind,
            attempt_index=max(0, _safe_int(body.get("attempt_index"))),
            failed=bool(failed),
            recovered_after_retry=bool(recovered_after_retry),
            blocked_by_policy=bool(blocked_by_policy),
            approval_required=bool(approval_required),
            operator_required=bool(operator_required),
            timestamp=_text(body.get("timestamp") or body.get("occurred_at") or body.get("created_at")),
        )

    def event_from_feedback(
        self,
        *,
        tenant_id: str,
        business_id: str,
        action_type: str,
        retry_kind: str,
        result_error: str | None,
        attempt_index: int,
        feedback: Mapping[str, Any] | None = None,
        recovery_mode: str | None = None,
    ) -> FailureEvent:
        body = _safe_dict(feedback)
        retry_kind_token = _text_lower(retry_kind)
        blocked_by_policy = _safe_bool(body.get("blocked_by_policy"))
        approval_required = _safe_bool(body.get("approval_required"))
        operator_required = _safe_bool(body.get("operator_required")) or approval_required or retry_kind_token == "operator_required"
        return FailureEvent(
            tenant_id=_text(tenant_id),
            business_id=_text(business_id),
            action_type=_text(action_type),
            error_family=self._classifier.classify(result_error) or "unknown",
            error_message=_text(result_error),
            capability=_text(body.get("capability") or body.get("capability_key")),
            service_name=_text(body.get("service_name") or body.get("service") or body.get("runner_name")),
            recovery_mode=_text(recovery_mode or body.get("recovery_mode")),
            retry_kind=retry_kind_token,
            attempt_index=max(0, int(attempt_index)),
            failed=retry_kind_token != "success",
            recovered_after_retry=retry_kind_token == "success" and max(0, int(attempt_index)) > 0,
            blocked_by_policy=bool(blocked_by_policy),
            approval_required=bool(approval_required),
            operator_required=bool(operator_required),
            timestamp=_text(body.get("timestamp") or body.get("occurred_at") or body.get("created_at")),
        )

    def _group_key(self, event: FailureEvent) -> tuple[str, str, str, str]:
        return (
            event.action_type or "",
            event.error_family or "unknown",
            event.capability or "",
            event.service_name or "",
        )

    def _severity(
        self,
        *,
        total_failures: int,
        consecutive_failures: int,
        recovered_after_retry_rate: float,
        operator_pressure_rate: float,
        policy_block_rate: float,
    ) -> str:
        if total_failures >= self._quarantine_threshold and consecutive_failures >= 3 and recovered_after_retry_rate <= 0.15:
            return "critical"
        if total_failures >= self._high_severity_threshold or operator_pressure_rate >= 0.50 or policy_block_rate >= 0.50:
            return "high"
        if total_failures >= self._recurring_threshold:
            return "medium"
        return "low"

    def _recommended_backoff_floor_seconds(self, *, error_family: str, total_failures: int, consecutive_failures: int) -> int:
        family = _text_lower(error_family)
        pressure = max(int(total_failures), int(consecutive_failures))
        if family == "rate_limit":
            return min(900, max(30, 30 * pressure))
        if family == "transport":
            return min(300, max(10, 10 * pressure))
        if family in {"authorization", "validation"}:
            return 0
        return min(180, max(5, 5 * pressure))

    def _recommended_max_attempts(
        self,
        *,
        error_family: str,
        success_after_retry_rate: float,
        total_failures: int,
        consecutive_failures: int,
    ) -> int:
        family = _text_lower(error_family)
        if family in {"authorization", "validation"}:
            return 1
        if family == "rate_limit":
            if total_failures >= self._high_severity_threshold and success_after_retry_rate < 0.35:
                return 2
            return 3
        if family == "transport":
            if consecutive_failures >= 3 and success_after_retry_rate < 0.30:
                return 2
            return 3
        if success_after_retry_rate < 0.20 and total_failures >= self._recurring_threshold:
            return 2
        return 3

    def detect(
        self,
        *,
        events: Iterable[Mapping[str, Any] | FailureEvent],
        tenant_id: str = "",
        business_id: str = "",
    ) -> FailurePatternReport:
        normalized: list[FailureEvent] = []
        for item in events:
            if isinstance(item, FailureEvent):
                normalized.append(item)
            elif isinstance(item, Mapping):
                normalized.append(self._normalize_event(item))
        groups: dict[tuple[str, str, str, str], list[FailureEvent]] = {}
        for event in normalized:
            groups.setdefault(self._group_key(event), []).append(event)
        patterns: list[FailurePattern] = []
        total_failures = 0
        for group in groups.values():
            ordered = list(group)
            failures = [event for event in ordered if event.failed]
            total_failures += len(failures)
            if not failures:
                continue
            last = failures[-1]
            recovered_after_retry_count = sum(1 for item in failures if item.recovered_after_retry)
            operator_required_count = sum(1 for item in failures if item.operator_required)
            policy_block_count = sum(1 for item in failures if item.blocked_by_policy or item.approval_required)
            consecutive_failures = 0
            for event in reversed(ordered):
                if event.failed:
                    consecutive_failures += 1
                else:
                    break
            success_after_retry_rate = _clamp_unit(recovered_after_retry_count / float(len(failures)))
            operator_pressure_rate = _clamp_unit(operator_required_count / float(len(failures)))
            policy_block_rate = _clamp_unit(policy_block_count / float(len(failures)))
            severity = self._severity(
                total_failures=len(failures),
                consecutive_failures=consecutive_failures,
                recovered_after_retry_rate=success_after_retry_rate,
                operator_pressure_rate=operator_pressure_rate,
                policy_block_rate=policy_block_rate,
            )
            recurring = len(failures) >= self._recurring_threshold
            recommended_backoff_floor_seconds = self._recommended_backoff_floor_seconds(
                error_family=last.error_family,
                total_failures=len(failures),
                consecutive_failures=consecutive_failures,
            )
            recommended_max_attempts = self._recommended_max_attempts(
                error_family=last.error_family,
                success_after_retry_rate=success_after_retry_rate,
                total_failures=len(failures),
                consecutive_failures=consecutive_failures,
            )
            should_open_operator_handoff = operator_required_count > 0 or policy_block_count > 0 or last.error_family in {"authorization", "validation"}
            should_quarantine_capability = bool(last.capability) and severity == "critical" and success_after_retry_rate <= 0.15
            should_cooldown = recurring and recommended_backoff_floor_seconds > 0 and consecutive_failures >= 2
            timestamps = _dedupe_preserve_order([item.timestamp for item in failures if item.timestamp], limit=_MAX_TIMESTAMP_SAMPLES)
            sample_error = next((_bounded_error_sample(item.error_message) for item in failures if item.error_message), "")
            patterns.append(
                FailurePattern(
                    tenant_id=_text(tenant_id or last.tenant_id),
                    business_id=_text(business_id or last.business_id),
                    action_type=last.action_type,
                    error_family=last.error_family or "unknown",
                    capability=last.capability,
                    service_name=last.service_name,
                    total_failures=len(failures),
                    consecutive_failures=consecutive_failures,
                    total_events=len(ordered),
                    recovered_after_retry_count=recovered_after_retry_count,
                    operator_required_count=operator_required_count,
                    policy_block_count=policy_block_count,
                    max_attempt_index=max(max(0, item.attempt_index) for item in failures),
                    recurring=bool(recurring),
                    severity=severity,
                    sample_error=sample_error,
                    timestamps=timestamps,
                    recommended_backoff_floor_seconds=int(recommended_backoff_floor_seconds),
                    recommended_max_attempts=max(1, int(recommended_max_attempts)),
                    should_open_operator_handoff=bool(should_open_operator_handoff),
                    should_quarantine_capability=bool(should_quarantine_capability),
                    should_cooldown=bool(should_cooldown),
                    evidence_only=True,
                    must_not_issue_decision=True,
                )
            )
        patterns.sort(
            key=lambda item: (
                _severity_rank(item.severity),
                item.total_failures,
                item.consecutive_failures,
                item.operator_required_count,
                item.policy_block_count,
                item.action_type,
                item.error_family,
                item.capability,
                item.service_name,
            ),
            reverse=True,
        )
        return FailurePatternReport(
            tenant_id=_text(tenant_id),
            business_id=_text(business_id),
            patterns=tuple(patterns),
            total_events=len(normalized),
            total_failures=total_failures,
            recurring_pattern_count=sum(1 for item in patterns if item.recurring),
            high_severity_pattern_count=sum(1 for item in patterns if item.severity in {"high", "critical"}),
            evidence_only=True,
            must_not_issue_decision=True,
        )


__all__ = [
    "CANON_FAILURE_PATTERN_DETECTOR",
    "FAILURE_PATTERN_SCHEMA_VERSION",
    "FailureEvent",
    "FailurePattern",
    "FailurePatternDetector",
    "FailurePatternReport",
]
