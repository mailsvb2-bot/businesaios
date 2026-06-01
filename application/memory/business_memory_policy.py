from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from runtime.platform.business_memory.second_brain_boundary import sanitize_business_memory_payload

CANON_BUSINESS_MEMORY_POLICY = True


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return int(parsed) if parsed >= 0 else int(default)


def _safe_float(value: object, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        item = _text(raw)
        if not item:
            continue
        marker = item.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


@dataclass(frozen=True)
class BusinessMemoryPolicy:
    """
    Canonical policy owner for business-memory compaction.

    Hard rules:
    - evidence-only;
    - no planning;
    - no routing;
    - no effect unlock;
    - no action issuance;
    - no second brain.
    """

    max_recent_runs: int = 20
    max_active_goals: int = 12
    max_signals: int = 24
    max_failures: int = 16
    max_wins: int = 16
    max_anti_patterns: int = 16

    max_profile_fields: int = 64
    max_constraint_fields: int = 64
    max_preferences: int = 32

    max_text_length: int = 256
    max_summary_length: int = 512
    max_key_length: int = 96
    max_source_run_ids: int = 8
    max_feedback_fields: int = 48
    max_nested_mapping_items: int = 12
    max_nested_sequence_items: int = 12
    max_nested_depth: int = 2

    min_pattern_frequency: int = 2
    confidence_cap: float = 0.99
    freshness_half_life_runs: int = 8

    anti_pattern_confidence_threshold: float = 0.55
    anti_pattern_frequency_threshold: float = 0.30

    trend_window_runs: int = 5

    approx_target_payload_bytes: int = 32_000
    approx_hard_payload_bytes: int = 64_000

    save_lock_timeout_seconds: float = 5.0
    save_lock_retry_delay_seconds: float = 0.05

    def sanitize_text(self, value: object, *, max_length: int | None = None) -> str:
        text = _text(value)
        limit = int(max_length if max_length is not None else self.max_text_length)
        if limit <= 0:
            return ""
        return text if len(text) <= limit else text[:limit]

    def sanitize_key(self, value: object) -> str:
        return self.sanitize_text(value, max_length=self.max_key_length)

    def sanitize_mapping(
        self,
        payload: Mapping[str, Any] | None,
        *,
        limit: int,
        value_max_length: int | None = None,
    ) -> dict[str, str]:
        if not payload:
            return {}

        result: dict[str, str] = {}
        for raw_key, raw_value in dict(payload).items():
            key = self.sanitize_key(raw_key)
            value = self.sanitize_text(raw_value, max_length=value_max_length)
            if not key or not value:
                continue
            result[key] = value
            if len(result) >= int(limit):
                break
        return dict(sorted(result.items()))

    def sanitize_goal_list(self, values: Sequence[str] | None) -> tuple[str, ...]:
        cleaned = [self.sanitize_text(item, max_length=self.max_summary_length) for item in list(values or [])]
        deduped = _dedupe_preserve_order(cleaned)
        return tuple(item for item in deduped[: int(self.max_active_goals)] if item)

    def sanitize_run_ids(self, values: Sequence[str] | None) -> tuple[str, ...]:
        cleaned = [self.sanitize_text(item, max_length=128) for item in list(values or [])]
        return tuple(_dedupe_preserve_order(cleaned)[: int(self.max_source_run_ids)])

    def sanitize_scalar_sequence(
        self,
        values: Sequence[object] | None,
        *,
        item_max_length: int = 160,
        limit: int | None = None,
    ) -> list[str]:
        bounded_limit = int(limit if limit is not None else self.max_nested_sequence_items)
        cleaned = [self.sanitize_text(item, max_length=item_max_length) for item in list(values or [])]
        return [item for item in _dedupe_preserve_order(cleaned)[:bounded_limit] if item]

    def sanitize_jsonish(self, value: object, *, depth: int = 0) -> Any:
        if depth >= int(self.max_nested_depth):
            if isinstance(value, (str, int, float, bool)) or value is None:
                return self.sanitize_text(value, max_length=self.max_summary_length) if isinstance(value, str) else value
            return self.sanitize_text(repr(value), max_length=160)

        if isinstance(value, str):
            return self.sanitize_text(value, max_length=self.max_summary_length)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, Mapping):
            result: dict[str, Any] = {}
            for raw_key, raw_value in list(dict(value).items())[: int(self.max_nested_mapping_items)]:
                key = self.sanitize_key(raw_key)
                if not key:
                    continue
                cleaned = self.sanitize_jsonish(raw_value, depth=depth + 1)
                if cleaned == "" or cleaned == [] or cleaned == {}:
                    continue
                result[key] = cleaned
            return result
        if isinstance(value, (list, tuple, set)):
            result: list[Any] = []
            for item in list(value)[: int(self.max_nested_sequence_items)]:
                cleaned = self.sanitize_jsonish(item, depth=depth + 1)
                if cleaned == "" or cleaned == [] or cleaned == {}:
                    continue
                result.append(cleaned)
            return result
        return self.sanitize_text(repr(value), max_length=160)

    def sanitize_feedback_payload(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        if not payload:
            return {}

        result: dict[str, Any] = {}
        for raw_key, raw_value in dict(payload).items():
            key = self.sanitize_key(raw_key)
            if not key:
                continue
            value = self.sanitize_jsonish(raw_value)
            if value == "" or value == [] or value == {}:
                continue
            result[key] = value
            if len(result) >= int(self.max_feedback_fields):
                break
        sanitized = sanitize_business_memory_payload(result)
        return dict(sanitized or {})

    def normalize_confidence(self, value: object) -> float:
        parsed = _safe_float(value, default=0.0)
        if parsed < 0.0:
            return 0.0
        if parsed > float(self.confidence_cap):
            return float(self.confidence_cap)
        return float(parsed)

    def normalize_frequency(self, value: object) -> float:
        parsed = _safe_float(value, default=0.0)
        if parsed < 0.0:
            return 0.0
        if parsed > 1.0:
            return 1.0
        return float(parsed)

    def normalize_unit_interval(self, value: object) -> float:
        return self.normalize_frequency(value)

    def clamp_non_negative_int(self, value: object, *, default: int = 0) -> int:
        return _safe_int(value, default=default)

    def clamp_goal_score(self, value: object) -> float:
        return self.normalize_unit_interval(value)

    def pattern_should_survive(self, *, count: int, confidence: float, freshness: float) -> bool:
        return (
            int(count) >= int(self.min_pattern_frequency)
            or float(confidence) >= 0.50
            or float(freshness) >= 0.75
        )

    def pattern_rank_score(
        self,
        *,
        confidence: float,
        freshness: float,
        frequency: float,
        count: int,
    ) -> tuple[float, float, float, int]:
        return (float(confidence), float(freshness), float(frequency), int(count))

    def anti_pattern_should_exist(self, *, confidence: float, frequency: float) -> bool:
        return (
            float(confidence) >= float(self.anti_pattern_confidence_threshold)
            or float(frequency) >= float(self.anti_pattern_frequency_threshold)
        )

    def estimate_half_life_decay(self, *, age_in_runs: int) -> float:
        age = max(0, int(age_in_runs))
        half_life = max(1, int(self.freshness_half_life_runs))
        return float(0.5 ** (age / half_life))


__all__ = ["CANON_BUSINESS_MEMORY_POLICY", "BusinessMemoryPolicy"]
