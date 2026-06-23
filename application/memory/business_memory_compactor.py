from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any
from collections.abc import Iterable

from application.memory.business_memory_policy import BusinessMemoryPolicy
from application.memory.business_operating_memory_types import (
    AntiPatternRecord,
    BusinessMemoryRunRecord,
    MemoryTrendSnapshot,
    PatternEvidence,
    SignalMemoryRecord,
)


CANON_BUSINESS_MEMORY_COMPACTOR = True


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _serialize_size_bytes(payload: object) -> int:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return len(encoded)


@dataclass(frozen=True)
class BusinessMemoryCompactionReport:
    before_recent_runs: int
    after_recent_runs: int
    before_failures: int
    after_failures: int
    before_wins: int
    after_wins: int
    before_signals: int
    after_signals: int
    before_anti_patterns: int
    after_anti_patterns: int
    approx_payload_bytes: int
    target_payload_bytes: int
    hard_payload_bytes: int
    trimmed_for_size_budget: bool = False
    hard_trim_applied: bool = False


@dataclass(frozen=True)
class BusinessMemoryCompactor:
    """Canonical evidence compactor. Never becomes a planner or decider."""

    policy: BusinessMemoryPolicy = field(default_factory=BusinessMemoryPolicy)

    def compact(self, memory: Any) -> Any:
        compacted, _ = self.compact_with_report(memory)
        return compacted

    def compact_with_report(
        self,
        memory: Any,
    ) -> tuple[Any, BusinessMemoryCompactionReport]:
        recent_runs = self._compact_recent_runs(memory.recent_runs)
        signal_memory = self._compact_signals(memory.signal_memory)
        recurring_failures = self._compact_patterns(
            patterns=memory.recurring_failures,
            limit=self.policy.max_failures,
            total_runs=memory.total_runs,
            recent_runs=recent_runs,
        )
        recurring_wins = self._compact_patterns(
            patterns=memory.recurring_wins,
            limit=self.policy.max_wins,
            total_runs=memory.total_runs,
            recent_runs=recent_runs,
        )
        anti_patterns = self._derive_anti_patterns(recurring_failures=recurring_failures)
        trends = self._build_trends(recent_runs=recent_runs, signal_memory=signal_memory)

        compacted = self._rebuild_memory(
            memory=memory,
            recent_runs=recent_runs,
            signal_memory=signal_memory,
            recurring_failures=recurring_failures,
            recurring_wins=recurring_wins,
            anti_patterns=anti_patterns,
            trends=trends,
        )

        approx_size = self._estimate_payload_bytes(compacted)
        trimmed_for_size_budget = False
        hard_trim_applied = False

        if approx_size > int(self.policy.approx_target_payload_bytes):
            compacted = self._soft_trim(compacted)
            approx_size = self._estimate_payload_bytes(compacted)
            trimmed_for_size_budget = True

        if approx_size > int(self.policy.approx_hard_payload_bytes):
            compacted = self._hard_trim(compacted)
            approx_size = self._estimate_payload_bytes(compacted)
            trimmed_for_size_budget = True
            hard_trim_applied = True

        report = BusinessMemoryCompactionReport(
            before_recent_runs=len(memory.recent_runs),
            after_recent_runs=len(compacted.recent_runs),
            before_failures=len(memory.recurring_failures),
            after_failures=len(compacted.recurring_failures),
            before_wins=len(memory.recurring_wins),
            after_wins=len(compacted.recurring_wins),
            before_signals=len(memory.signal_memory),
            after_signals=len(compacted.signal_memory),
            before_anti_patterns=len(memory.anti_patterns),
            after_anti_patterns=len(compacted.anti_patterns),
            approx_payload_bytes=approx_size,
            target_payload_bytes=int(self.policy.approx_target_payload_bytes),
            hard_payload_bytes=int(self.policy.approx_hard_payload_bytes),
            trimmed_for_size_budget=trimmed_for_size_budget,
            hard_trim_applied=hard_trim_applied,
        )
        return compacted, report

    def _rebuild_memory(
        self,
        *,
        memory: Any,
        recent_runs: list[BusinessMemoryRunRecord],
        signal_memory: list[SignalMemoryRecord],
        recurring_failures: list[PatternEvidence],
        recurring_wins: list[PatternEvidence],
        anti_patterns: list[AntiPatternRecord],
        trends: MemoryTrendSnapshot | None,
    ) -> Any:
        return type(memory)(
            schema_version=int(getattr(memory, "schema_version", 2)),
            tenant_id=self.policy.sanitize_text(memory.tenant_id, max_length=128),
            business_id=self.policy.sanitize_text(memory.business_id, max_length=128),
            business_profile=self.policy.sanitize_mapping(
                memory.business_profile,
                limit=self.policy.max_profile_fields,
            ),
            active_goals=self.policy.sanitize_goal_list(list(memory.active_goals)),
            operating_constraints=self.policy.sanitize_mapping(
                memory.operating_constraints,
                limit=self.policy.max_constraint_fields,
            ),
            learned_preferences=self.policy.sanitize_mapping(
                memory.learned_preferences,
                limit=self.policy.max_preferences,
            ),
            signal_memory=tuple(signal_memory),
            recurring_failures=tuple(recurring_failures),
            recurring_wins=tuple(recurring_wins),
            anti_patterns=tuple(anti_patterns),
            trends=trends,
            last_feedback=self.policy.sanitize_feedback_payload(memory.last_feedback),
            last_run=None if memory.last_run is None else self._sanitize_run_record(memory.last_run),
            recent_runs=tuple(recent_runs),
            total_runs=self.policy.clamp_non_negative_int(memory.total_runs),
            completed_runs=self.policy.clamp_non_negative_int(memory.completed_runs),
            failed_runs=self.policy.clamp_non_negative_int(memory.failed_runs),
            average_goal_score=self.policy.clamp_goal_score(memory.average_goal_score),
        )

    def _compact_recent_runs(self, rows: Iterable[BusinessMemoryRunRecord]) -> list[BusinessMemoryRunRecord]:
        result: list[BusinessMemoryRunRecord] = []
        seen_run_ids: set[str] = set()
        for row in list(rows):
            item = self._sanitize_run_record(row)
            if not item.run_id or item.run_id in seen_run_ids:
                continue
            seen_run_ids.add(item.run_id)
            result.append(item)
            if len(result) >= int(self.policy.max_recent_runs):
                break
        return result

    def _sanitize_run_record(self, row: BusinessMemoryRunRecord) -> BusinessMemoryRunRecord:
        fingerprint = self.policy.sanitize_mapping(row.fingerprint, limit=12, value_max_length=96)
        return BusinessMemoryRunRecord(
            run_id=self.policy.sanitize_text(row.run_id, max_length=128),
            goal=self.policy.sanitize_text(row.goal, max_length=self.policy.max_summary_length),
            completed=bool(row.completed),
            stop_reason=self.policy.sanitize_text(row.stop_reason, max_length=96),
            goal_score=self.policy.clamp_goal_score(row.goal_score),
            step_count=self.policy.clamp_non_negative_int(row.step_count),
            summary=self.policy.sanitize_text(row.summary, max_length=self.policy.max_summary_length),
            channel=self.policy.sanitize_text(row.channel, max_length=96),
            region=self.policy.sanitize_text(row.region, max_length=96),
            product_name=self.policy.sanitize_text(row.product_name, max_length=128),
            goal_family=self.policy.sanitize_text(row.goal_family, max_length=96) or "general",
            fingerprint=fingerprint,
            recorded_at=self.policy.sanitize_text(row.recorded_at, max_length=64) or None,
        )

    def _compact_signals(self, rows: Iterable[SignalMemoryRecord]) -> list[SignalMemoryRecord]:
        merged: dict[str, SignalMemoryRecord] = {}
        for raw in list(rows):
            item = SignalMemoryRecord(
                kind=self.policy.sanitize_text(raw.kind, max_length=64) or "signal",
                name=self.policy.sanitize_text(raw.name, max_length=128) or "signal",
                last_value=self.policy.sanitize_text(raw.last_value, max_length=160),
                count=max(1, self.policy.clamp_non_negative_int(raw.count, default=1)),
                last_seen_run_id=self.policy.sanitize_text(raw.last_seen_run_id, max_length=128) or None,
                last_seen_at=self.policy.sanitize_text(raw.last_seen_at, max_length=64) or None,
                trend=self.policy.sanitize_text(raw.trend, max_length=32) or "unknown",
            )
            key = item.key()
            previous = merged.get(key)
            if previous is None:
                merged[key] = item
                continue
            merged[key] = SignalMemoryRecord(
                kind=item.kind,
                name=item.name,
                last_value=item.last_value or previous.last_value,
                count=max(int(previous.count), int(item.count)),
                last_seen_run_id=item.last_seen_run_id or previous.last_seen_run_id,
                last_seen_at=item.last_seen_at or previous.last_seen_at,
                trend=item.trend if item.trend != "unknown" else previous.trend,
            )
        ranked = sorted(merged.values(), key=lambda item: (-int(item.count), item.kind, item.name))
        return ranked[: int(self.policy.max_signals)]

    def _compact_patterns(
        self,
        *,
        patterns: Iterable[PatternEvidence],
        limit: int,
        total_runs: int,
        recent_runs: list[BusinessMemoryRunRecord],
    ) -> list[PatternEvidence]:
        known_recent_ids = [row.run_id for row in recent_runs if row.run_id]
        normalized: list[PatternEvidence] = []
        for raw in list(patterns):
            item = self._sanitize_pattern(raw)
            item = self._apply_recency_decay(pattern=item, known_recent_ids=known_recent_ids)
            frequency = self._normalized_frequency(
                count=item.count,
                explicit_frequency=item.frequency,
                total_runs=total_runs,
            )
            candidate = PatternEvidence(
                key=item.key,
                count=max(1, int(item.count)),
                last_seen_run_id=item.last_seen_run_id,
                last_seen_at=item.last_seen_at,
                confidence=self.policy.normalize_confidence(item.confidence),
                frequency=frequency,
                freshness=self.policy.normalize_unit_interval(item.freshness),
                source_run_ids=self.policy.sanitize_run_ids(item.source_run_ids),
            )
            if self.policy.pattern_should_survive(
                count=candidate.count,
                confidence=candidate.confidence,
                freshness=candidate.freshness,
            ):
                normalized.append(candidate)
        normalized.sort(
            key=lambda item: self.policy.pattern_rank_score(
                confidence=item.confidence,
                freshness=item.freshness,
                frequency=item.frequency,
                count=item.count,
            ),
            reverse=True,
        )
        return normalized[: int(limit)]

    def _sanitize_pattern(self, raw: PatternEvidence) -> PatternEvidence:
        return PatternEvidence(
            key=self.policy.sanitize_text(raw.key, max_length=128),
            count=max(1, self.policy.clamp_non_negative_int(raw.count, default=1)),
            last_seen_run_id=self.policy.sanitize_text(raw.last_seen_run_id, max_length=128) or None,
            last_seen_at=self.policy.sanitize_text(raw.last_seen_at, max_length=64) or None,
            confidence=self.policy.normalize_confidence(raw.confidence),
            frequency=self.policy.normalize_unit_interval(raw.frequency),
            freshness=self.policy.normalize_unit_interval(raw.freshness),
            source_run_ids=self.policy.sanitize_run_ids(raw.source_run_ids),
        )

    def _apply_recency_decay(
        self,
        *,
        pattern: PatternEvidence,
        known_recent_ids: list[str],
    ) -> PatternEvidence:
        freshness = self.policy.normalize_unit_interval(pattern.freshness)
        if not known_recent_ids:
            return PatternEvidence(
                key=pattern.key,
                count=pattern.count,
                last_seen_run_id=pattern.last_seen_run_id,
                last_seen_at=pattern.last_seen_at,
                confidence=pattern.confidence,
                frequency=pattern.frequency,
                freshness=freshness,
                source_run_ids=pattern.source_run_ids,
            )
        run_id_to_age = {run_id: idx for idx, run_id in enumerate(known_recent_ids)}
        age_candidates: list[int] = []
        if pattern.last_seen_run_id and pattern.last_seen_run_id in run_id_to_age:
            age_candidates.append(run_id_to_age[pattern.last_seen_run_id])
        for run_id in pattern.source_run_ids:
            if run_id in run_id_to_age:
                age_candidates.append(run_id_to_age[run_id])
        if not age_candidates:
            decayed = freshness * self.policy.estimate_half_life_decay(age_in_runs=max(1, len(known_recent_ids)))
        else:
            best_age = min(age_candidates)
            decayed = max(freshness, self.policy.estimate_half_life_decay(age_in_runs=best_age))
        confidence = self.policy.normalize_confidence(max(float(pattern.confidence), float(decayed) * 0.85))
        return PatternEvidence(
            key=pattern.key,
            count=pattern.count,
            last_seen_run_id=pattern.last_seen_run_id,
            last_seen_at=pattern.last_seen_at,
            confidence=confidence,
            frequency=pattern.frequency,
            freshness=self.policy.normalize_unit_interval(decayed),
            source_run_ids=pattern.source_run_ids,
        )

    def _normalized_frequency(self, *, count: int, explicit_frequency: float, total_runs: int) -> float:
        if float(explicit_frequency) > 0.0:
            return self.policy.normalize_unit_interval(explicit_frequency)
        if int(total_runs) <= 0:
            return 0.0
        return self.policy.normalize_unit_interval(float(count) / float(total_runs))

    def _derive_anti_patterns(self, *, recurring_failures: list[PatternEvidence]) -> list[AntiPatternRecord]:
        result: list[AntiPatternRecord] = []
        for item in recurring_failures:
            if not self.policy.anti_pattern_should_exist(confidence=item.confidence, frequency=item.frequency):
                continue
            result.append(
                AntiPatternRecord(
                    key=item.key,
                    confidence=item.confidence,
                    frequency=item.frequency,
                    freshness=item.freshness,
                    source_run_ids=self.policy.sanitize_run_ids(item.source_run_ids),
                    reason="recurring_failure_pattern",
                )
            )
        result.sort(key=lambda item: (-float(item.confidence), -float(item.freshness), -float(item.frequency), item.key))
        return result[: int(self.policy.max_anti_patterns)]

    def _build_trends(
        self,
        *,
        recent_runs: list[BusinessMemoryRunRecord],
        signal_memory: list[SignalMemoryRecord],
    ) -> MemoryTrendSnapshot | None:
        window = list(recent_runs[: int(self.policy.trend_window_runs)])
        if not window:
            return None
        size = len(window)
        average_goal_score = sum(float(row.goal_score) for row in window) / float(size)
        failure_rate = sum(1 for row in window if not row.completed) / float(size)
        win_rate = sum(
            1
            for row in window
            if row.completed and (row.stop_reason == "goal_reached" or float(row.goal_score) >= 0.80)
        ) / float(size)
        oldest = window[-1]
        newest = window[0]
        return MemoryTrendSnapshot(
            window_size=size,
            goal_score_trend=self._direction(float(oldest.goal_score), float(newest.goal_score)),
            failure_trend=self._direction(
                1.0 if not oldest.completed else 0.0,
                1.0 if not newest.completed else 0.0,
                invert=True,
            ),
            win_trend=self._direction(
                1.0 if oldest.completed and (oldest.stop_reason == "goal_reached" or float(oldest.goal_score) >= 0.80) else 0.0,
                1.0 if newest.completed and (newest.stop_reason == "goal_reached" or float(newest.goal_score) >= 0.80) else 0.0,
            ),
            signal_trend="active" if signal_memory else "flat",
            average_goal_score_window=float(average_goal_score),
            failure_rate_window=float(failure_rate),
            win_rate_window=float(win_rate),
        )

    def _direction(self, first: float, last: float, *, invert: bool = False) -> str:
        delta = float(last) - float(first)
        if abs(delta) <= 1e-9:
            return "flat"
        if invert:
            return "up" if delta < 0.0 else "down"
        return "up" if delta > 0.0 else "down"

    def _soft_trim(self, memory: Any) -> Any:
        return self._rebuild_memory(
            memory=memory,
            recent_runs=list(memory.recent_runs[: max(10, int(self.policy.max_recent_runs // 2))]),
            signal_memory=list(memory.signal_memory[: max(8, int(self.policy.max_signals // 2))]),
            recurring_failures=list(memory.recurring_failures[: max(8, int(self.policy.max_failures // 2))]),
            recurring_wins=list(memory.recurring_wins[: max(8, int(self.policy.max_wins // 2))]),
            anti_patterns=list(memory.anti_patterns[: max(8, int(self.policy.max_anti_patterns // 2))]),
            trends=memory.trends,
        )

    def _hard_trim(self, memory: Any) -> Any:
        return type(memory)(
            schema_version=int(getattr(memory, "schema_version", 2)),
            tenant_id=self.policy.sanitize_text(memory.tenant_id, max_length=128),
            business_id=self.policy.sanitize_text(memory.business_id, max_length=128),
            business_profile=dict(list(memory.business_profile.items())[:16]),
            active_goals=tuple(list(memory.active_goals)[:6]),
            operating_constraints=dict(list(memory.operating_constraints.items())[:16]),
            learned_preferences=dict(list(memory.learned_preferences.items())[:12]),
            signal_memory=tuple(list(memory.signal_memory)[:8]),
            recurring_failures=tuple(list(memory.recurring_failures)[:8]),
            recurring_wins=tuple(list(memory.recurring_wins)[:8]),
            anti_patterns=tuple(list(memory.anti_patterns)[:8]),
            trends=memory.trends,
            last_feedback=self.policy.sanitize_feedback_payload(memory.last_feedback),
            last_run=None if memory.last_run is None else self._sanitize_run_record(memory.last_run),
            recent_runs=tuple(list(memory.recent_runs)[:8]),
            total_runs=self.policy.clamp_non_negative_int(memory.total_runs),
            completed_runs=self.policy.clamp_non_negative_int(memory.completed_runs),
            failed_runs=self.policy.clamp_non_negative_int(memory.failed_runs),
            average_goal_score=self.policy.clamp_goal_score(memory.average_goal_score),
        )

    def _estimate_payload_bytes(self, memory: Any) -> int:
        return _serialize_size_bytes(asdict(memory))


__all__ = [
    "CANON_BUSINESS_MEMORY_COMPACTOR",
    "BusinessMemoryCompactionReport",
    "BusinessMemoryCompactor",
]
