from __future__ import annotations

from typing import Any, Iterable, Mapping

from execution.business_memory_policy import BusinessMemoryPolicy
from execution.business_operating_memory_types import (
    AntiPatternRecord,
    BusinessMemoryRunRecord,
    MemoryTrendSnapshot,
    PatternEvidence,
    SignalMemoryRecord,
)

BUSINESS_MEMORY_SCHEMA_VERSION = 2
CANON_BUSINESS_MEMORY_STORE_SUPPORT = True


def text(value: object) -> str:
    return str(value or "").strip()


def safe_key(value: object, *, fallback: str) -> str:
    normalized = text(value)
    if not normalized:
        return fallback
    return normalized.replace("\\", "_").replace("/", "_").replace(":", "_").replace(" ", "_")


def safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        normalized = text(raw)
        if not normalized:
            continue
        marker = normalized.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def safe_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def safe_rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, (list, tuple)):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def optional_text(policy: BusinessMemoryPolicy, value: object, *, max_length: int) -> str | None:
    normalized = policy.sanitize_text(value, max_length=max_length)
    return normalized or None


def normalize_pattern_rows(rows: object) -> list[Any]:
    normalized: list[Any] = []
    for raw in list(rows or []):
        if isinstance(raw, Mapping):
            item = dict(raw)
            if item.get("action") and not item.get("key"):
                item["key"] = item.get("action")
            normalized.append(item)
        else:
            normalized.append(raw)
    return normalized


def dedupe_recent_runs(rows: tuple[BusinessMemoryRunRecord, ...]) -> tuple[BusinessMemoryRunRecord, ...]:
    seen: set[str] = set()
    result: list[BusinessMemoryRunRecord] = []
    for record in reversed(rows):
        marker = record.run_id.casefold()
        if not marker or marker in seen:
            continue
        seen.add(marker)
        result.append(record)
    result.reverse()
    return tuple(result)


def signal_record_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> SignalMemoryRecord:
    return SignalMemoryRecord(
        kind=policy.sanitize_text(row.get("kind") or row.get("type") or "signal", max_length=64) or "signal",
        name=policy.sanitize_text(row.get("name") or row.get("key") or "signal", max_length=128) or "signal",
        last_value=policy.sanitize_text(row.get("last_value") or row.get("value") or "", max_length=160),
        count=max(1, policy.clamp_non_negative_int(row.get("count"), default=1)),
        last_seen_run_id=optional_text(policy, row.get("last_seen_run_id"), max_length=128),
        last_seen_at=optional_text(policy, row.get("last_seen_at"), max_length=64),
        trend=policy.sanitize_text(row.get("trend") or "unknown", max_length=32) or "unknown",
    )


def pattern_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> PatternEvidence:
    return PatternEvidence(
        key=policy.sanitize_text(row.get("key") or row.get("action") or "pattern", max_length=160),
        count=max(1, policy.clamp_non_negative_int(row.get("count"), default=1)),
        last_seen_run_id=optional_text(policy, row.get("last_seen_run_id"), max_length=128),
        last_seen_at=optional_text(policy, row.get("last_seen_at"), max_length=64),
        confidence=policy.normalize_confidence(row.get("confidence")),
        frequency=policy.normalize_frequency(row.get("frequency")),
        freshness=policy.normalize_unit_interval(row.get("freshness")),
        source_run_ids=tuple(
            policy.sanitize_text(item, max_length=128)
            for item in list(row.get("source_run_ids") or [])
            if policy.sanitize_text(item, max_length=128)
        ),
    )


def anti_pattern_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> AntiPatternRecord:
    return AntiPatternRecord(
        key=policy.sanitize_text(row.get("key"), max_length=128),
        confidence=policy.normalize_confidence(row.get("confidence")),
        frequency=policy.normalize_frequency(row.get("frequency")),
        freshness=policy.normalize_unit_interval(row.get("freshness")),
        source_run_ids=policy.sanitize_run_ids(row.get("source_run_ids") or []),
        reason=policy.sanitize_text(row.get("reason"), max_length=128),
    )


def run_record_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> BusinessMemoryRunRecord:
    return BusinessMemoryRunRecord(
        run_id=policy.sanitize_text(row.get("run_id"), max_length=128),
        goal=policy.sanitize_text(row.get("goal"), max_length=policy.max_summary_length),
        completed=bool(row.get("completed")),
        stop_reason=policy.sanitize_text(row.get("stop_reason"), max_length=96),
        goal_score=policy.clamp_goal_score(row.get("goal_score")),
        step_count=policy.clamp_non_negative_int(row.get("step_count")),
        summary=policy.sanitize_text(row.get("summary"), max_length=policy.max_summary_length),
        channel=policy.sanitize_text(row.get("channel"), max_length=96),
        region=policy.sanitize_text(row.get("region"), max_length=96),
        product_name=policy.sanitize_text(row.get("product_name"), max_length=128),
        goal_family=policy.sanitize_text(row.get("goal_family") or "general", max_length=96) or "general",
        fingerprint=policy.sanitize_mapping(row.get("fingerprint"), limit=12),
        recorded_at=optional_text(policy, row.get("recorded_at"), max_length=64),
    )


def trend_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> MemoryTrendSnapshot:
    return MemoryTrendSnapshot(
        window_size=policy.clamp_non_negative_int(row.get("window_size") or row.get("rolling_window"), default=0),
        goal_score_trend=policy.sanitize_text(row.get("goal_score_trend") or "flat", max_length=16) or "flat",
        failure_trend=policy.sanitize_text(row.get("failure_trend") or "flat", max_length=16) or "flat",
        win_trend=policy.sanitize_text(row.get("win_trend") or "flat", max_length=16) or "flat",
        signal_trend=policy.sanitize_text(row.get("signal_trend") or "flat", max_length=16) or "flat",
        average_goal_score_window=policy.clamp_goal_score(row.get("average_goal_score_window")),
        failure_rate_window=policy.normalize_unit_interval(row.get("failure_rate_window")),
        win_rate_window=policy.normalize_unit_interval(row.get("win_rate_window")),
    )


def migrate_business_memory_payload(payload: dict[str, Any], *, policy: BusinessMemoryPolicy) -> dict[str, Any]:
    migrated = dict(payload or {})
    migrated["schema_version"] = BUSINESS_MEMORY_SCHEMA_VERSION

    if not isinstance(migrated.get("business_profile"), Mapping):
        fallback_profile = migrated.get("aggregated_business_profile")
        if not isinstance(fallback_profile, Mapping):
            fallback_profile = migrated.get("profile")
        migrated["business_profile"] = dict(fallback_profile) if isinstance(fallback_profile, Mapping) else {}
    if not isinstance(migrated.get("operating_constraints"), Mapping):
        migrated["operating_constraints"] = {}
    if not isinstance(migrated.get("learned_preferences"), Mapping):
        migrated["learned_preferences"] = {}

    if migrated.get("signal_memory") is None and migrated.get("key_signals"):
        rows: list[dict[str, Any]] = []
        for item in list(migrated.get("key_signals") or []):
            item_text = text(item)
            if not item_text:
                continue
            parts = [part.strip() for part in item_text.split("|")]
            rows.append(
                {
                    "kind": parts[0] if len(parts) >= 1 else "signal",
                    "name": parts[1] if len(parts) >= 2 else (parts[0] if len(parts) >= 1 else "signal"),
                    "last_value": parts[2] if len(parts) >= 3 else item_text,
                    "count": 1,
                    "last_seen_run_id": None,
                    "last_seen_at": None,
                    "trend": "unknown",
                }
            )
        migrated["signal_memory"] = rows
    migrated.pop("key_signals", None)

    for field_name in ("recurring_failures", "recurring_wins"):
        raw = list(migrated.get(field_name) or [])
        if raw and isinstance(raw[0], str):
            migrated[field_name] = [
                {
                    "key": text(item),
                    "count": 1,
                    "last_seen_run_id": None,
                    "last_seen_at": None,
                    "confidence": 0.0,
                    "frequency": 0.0,
                    "freshness": 0.0,
                    "source_run_ids": [],
                }
                for item in raw
                if text(item)
            ]

    migrated["signal_memory"] = safe_rows(migrated.get("signal_memory"))
    migrated["recurring_failures"] = safe_rows(migrated.get("recurring_failures"))
    migrated["recurring_wins"] = safe_rows(migrated.get("recurring_wins"))
    migrated["anti_patterns"] = safe_rows(migrated.get("anti_patterns"))
    migrated["recent_runs"] = safe_rows(migrated.get("recent_runs"))
    migrated["last_feedback"] = policy.sanitize_feedback_payload(safe_mapping(migrated.get("last_feedback")))
    migrated["trends"] = safe_mapping(migrated.get("trends")) if isinstance(migrated.get("trends"), Mapping) else None
    migrated["last_run"] = safe_mapping(migrated.get("last_run")) if isinstance(migrated.get("last_run"), Mapping) else None

    for row in list(migrated.get("recent_runs") or []):
        row.setdefault("goal_family", "general")
        row.setdefault("fingerprint", {})
    if isinstance(migrated.get("last_run"), dict):
        migrated["last_run"].setdefault("goal_family", "general")
        migrated["last_run"].setdefault("fingerprint", {})
    return migrated
