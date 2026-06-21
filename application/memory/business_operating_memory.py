from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Iterable, Mapping

from application.memory.business_memory_lock import FileBusinessMemoryLock
from application.memory.business_memory_matcher import BusinessMemoryMatcher
from application.memory.business_memory_policy import BusinessMemoryPolicy
from application.memory.business_memory_taxonomy import BusinessMemoryTaxonomy, NormalizedFeedback
from application.memory.business_operating_memory_types import (
    AntiPatternRecord,
    BusinessMemoryRunRecord,
    MemoryTrendSnapshot,
    PatternEvidence,
    SignalMemoryRecord,
)
from execution.business_memory_store_support import (
    BUSINESS_MEMORY_SCHEMA_VERSION,
)
from execution.business_memory_store_support import (
    anti_pattern_from_row as _anti_pattern_from_row_owner,
)
from execution.business_memory_store_support import (
    dedupe as _dedupe_owner,
)
from execution.business_memory_store_support import (
    dedupe_recent_runs as _dedupe_recent_runs_owner,
)
from execution.business_memory_store_support import (
    migrate_business_memory_payload as _migrate_business_memory_payload_owner,
)
from execution.business_memory_store_support import (
    normalize_pattern_rows as _normalize_pattern_rows_owner,
)
from execution.business_memory_store_support import (
    pattern_from_row as _pattern_from_row_owner,
)
from execution.business_memory_store_support import (
    run_record_from_row as _run_record_from_row_owner,
)
from execution.business_memory_store_support import (
    safe_float as _safe_float_owner,
)
from execution.business_memory_store_support import (
    safe_int as _safe_int_owner,
)
from execution.business_memory_store_support import (
    safe_key as _safe_key_owner,
)
from execution.business_memory_store_support import (
    safe_mapping as _safe_mapping_owner,
)
from execution.business_memory_store_support import (
    safe_rows as _safe_rows_owner,
)
from execution.business_memory_store_support import (
    signal_record_from_row as _signal_record_from_row_owner,
)
from execution.business_memory_store_support import (
    text as _text_owner,
)
from execution.business_memory_store_support import (
    trend_from_row as _trend_from_row_owner,
)
from execution.canonical_persistence_vocabulary import canonical_memory_record

CANON_PERSISTENT_BUSINESS_OPERATING_MEMORY = True

def _text(value: object) -> str:
    return _text_owner(value)

def _safe_key(value: object, *, fallback: str) -> str:
    return _safe_key_owner(value, fallback=fallback)

def _safe_int(value: object, *, default: int = 0) -> int:
    return _safe_int_owner(value, default=default)

def _safe_float(value: object, *, default: float = 0.0) -> float:
    return _safe_float_owner(value, default=default)

def _dedupe(values: Iterable[str]) -> list[str]:
    return _dedupe_owner(values)

def _safe_mapping(value: object) -> dict[str, Any]:
    return _safe_mapping_owner(value)

def _safe_rows(value: object) -> list[dict[str, Any]]:
    return _safe_rows_owner(value)

def _normalize_pattern_rows(rows: object) -> list[Any]:
    return _normalize_pattern_rows_owner(rows)

def canonicalize_business_memory_payload(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
) -> BusinessOperatingMemory:
    from runtime.platform.business_memory.second_brain_boundary import sanitize_business_memory_payload

    canonical_policy = policy or BusinessMemoryPolicy()
    sanitized = dict(sanitize_business_memory_payload(dict(payload or {})) or {})
    for field_name in ("recurring_failures", "recurring_wins", "anti_patterns"):
        sanitized[field_name] = _normalize_pattern_rows(sanitized.get(field_name) or [])
    return BusinessOperatingMemory.from_dict(sanitized, policy=canonical_policy)

def project_business_memory_evidence(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
) -> dict[str, Any]:
    return canonicalize_business_memory_payload(payload, policy=policy).to_evidence_payload()

def project_business_memory_summary(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
) -> dict[str, Any]:
    return canonicalize_business_memory_payload(payload, policy=policy).to_summary_payload()

def project_business_memory_governance_summary(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
) -> dict[str, Any]:
    canonical_policy = policy or BusinessMemoryPolicy()
    raw_payload = dict(payload or {})
    summary = canonicalize_business_memory_payload(raw_payload, policy=canonical_policy).to_summary_payload()
    active_goals = sorted(canonical_policy.sanitize_goal_list(summary.get("active_goals") or []))
    recurring_failures = sorted(canonical_policy.sanitize_scalar_sequence(summary.get("recurring_failures") or [], item_max_length=128, limit=canonical_policy.max_failures))
    recurring_wins = sorted(canonical_policy.sanitize_scalar_sequence(summary.get("recurring_wins") or [], item_max_length=128, limit=canonical_policy.max_wins))
    anti_patterns = sorted(canonical_policy.sanitize_scalar_sequence(summary.get("anti_patterns") or raw_payload.get("anti_patterns") or [], item_max_length=128, limit=canonical_policy.max_anti_patterns))
    return {
        "tenant_id": canonical_policy.sanitize_text(summary.get("tenant_id"), max_length=128),
        "business_id": canonical_policy.sanitize_text(summary.get("business_id"), max_length=128),
        "business_profile": canonical_policy.sanitize_mapping(summary.get("business_profile"), limit=canonical_policy.max_profile_fields, value_max_length=canonical_policy.max_summary_length),
        "total_runs": canonical_policy.clamp_non_negative_int(summary.get("total_runs")),
        "completed_runs": canonical_policy.clamp_non_negative_int(summary.get("completed_runs")),
        "failed_runs": canonical_policy.clamp_non_negative_int(summary.get("failed_runs")),
        "average_goal_score": canonical_policy.clamp_goal_score(summary.get("average_goal_score")),
        "active_goals": active_goals,
        "learned_preferences": canonical_policy.sanitize_mapping(summary.get("learned_preferences"), limit=canonical_policy.max_preferences, value_max_length=canonical_policy.max_summary_length),
        "operating_constraints": canonical_policy.sanitize_mapping(summary.get("operating_constraints"), limit=canonical_policy.max_constraint_fields, value_max_length=canonical_policy.max_summary_length),
        "recurring_failures": recurring_failures,
        "recurring_wins": recurring_wins,
        "anti_patterns": anti_patterns,
        "trends": canonical_policy.sanitize_feedback_payload(summary.get("trends") or {}),
        "evidence_only": True,
        "must_not_issue_decision": True,
        "must_not_unlock_effects": True,
    }

def project_business_memory_profile(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
) -> dict[str, str]:
    canonical_policy = policy or BusinessMemoryPolicy()
    memory = canonicalize_business_memory_payload(payload, policy=canonical_policy)
    return canonical_policy.sanitize_mapping(memory.business_profile, limit=canonical_policy.max_profile_fields, value_max_length=canonical_policy.max_summary_length)

def project_business_memory_recent_runs(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    canonical_policy = policy or BusinessMemoryPolicy()
    memory = canonicalize_business_memory_payload(payload, policy=canonical_policy)
    bounded_limit = max(0, min(int(limit), int(canonical_policy.max_recent_runs)))
    return [asdict(item) for item in memory.recent_runs[:bounded_limit]]

def project_business_memory_patterns(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
) -> dict[str, list[dict[str, Any]]]:
    canonical_policy = policy or BusinessMemoryPolicy()
    state_context = canonicalize_business_memory_payload(payload, policy=canonical_policy).to_state_context_payload(policy=canonical_policy)
    return {
        "recurring_failures": [dict(item) for item in list(state_context.get("recurring_failures") or [])],
        "recurring_wins": [dict(item) for item in list(state_context.get("recurring_wins") or [])],
        "anti_patterns": [dict(item) for item in list(state_context.get("anti_patterns") or [])],
    }

def project_business_memory_state_context(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
) -> dict[str, Any]:
    canonical_policy = policy or BusinessMemoryPolicy()
    return canonicalize_business_memory_payload(payload, policy=canonical_policy).to_state_context_payload(policy=canonical_policy)

def project_business_memory_contract_bundle(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
    recent_runs_limit: int = 10,
) -> dict[str, Any]:
    canonical_policy = policy or BusinessMemoryPolicy()
    memory = canonicalize_business_memory_payload(payload, policy=canonical_policy)
    evidence = memory.to_evidence_payload()
    state_context = memory.to_state_context_payload(policy=canonical_policy)
    bounded_limit = max(0, min(int(recent_runs_limit), int(canonical_policy.max_recent_runs)))
    recent_runs = [asdict(item) for item in memory.recent_runs[:bounded_limit]]
    patterns = {
        "recurring_failures": [dict(item) for item in state_context.get("recurring_failures") or []],
        "recurring_wins": [dict(item) for item in state_context.get("recurring_wins") or []],
        "anti_patterns": [dict(item) for item in state_context.get("anti_patterns") or []],
    }
    return {
        "evidence": evidence,
        "summary": memory.to_summary_payload(),
        "governance_summary": project_business_memory_governance_summary(evidence, policy=canonical_policy),
        "profile": canonical_policy.sanitize_mapping(memory.business_profile, limit=canonical_policy.max_profile_fields, value_max_length=canonical_policy.max_summary_length),
        "recent_runs": recent_runs,
        "patterns": patterns,
        "state_context": state_context,
    }

def project_business_memory_feedback_snapshot(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
) -> dict[str, Any]:
    canonical_policy = policy or BusinessMemoryPolicy()
    bundle = project_business_memory_contract_bundle(payload, policy=canonical_policy, recent_runs_limit=5)
    evidence = dict(bundle.get("evidence") or {})
    governance_summary = dict(bundle.get("governance_summary") or {})
    recent_runs = list(bundle.get("recent_runs") or [])
    trends = dict(dict(bundle.get("state_context") or {}).get("trends") or {})
    recent_external_refs = canonical_policy.sanitize_scalar_sequence(evidence.get("recent_external_refs") or evidence.get("external_refs") or [], item_max_length=256, limit=8)
    verified_outcomes_count = canonical_policy.clamp_non_negative_int(evidence.get("verified_outcomes_count") or len(list(evidence.get("last_verified_outcomes") or [])))
    return {
        "business_profile": canonical_policy.sanitize_mapping(governance_summary.get("business_profile") or evidence.get("business_profile") or {}, limit=canonical_policy.max_profile_fields, value_max_length=canonical_policy.max_summary_length),
        "active_goals": list(governance_summary.get("active_goals") or []),
        "recent_external_refs": recent_external_refs,
        "verified_outcomes_count": verified_outcomes_count,
        "recent_runs": [dict(item) for item in recent_runs],
        "trends": canonical_policy.sanitize_feedback_payload(trends),
        "evidence_only": True,
        "must_not_issue_decision": True,
        "must_not_unlock_effects": True,
    }

@dataclass(frozen=True)
class BusinessOperatingMemory:
    schema_version: int
    tenant_id: str
    business_id: str
    business_profile: dict[str, str] = field(default_factory=dict)
    active_goals: tuple[str, ...] = ()
    operating_constraints: dict[str, str] = field(default_factory=dict)
    learned_preferences: dict[str, str] = field(default_factory=dict)
    signal_memory: tuple[SignalMemoryRecord, ...] = ()
    recurring_failures: tuple[PatternEvidence, ...] = ()
    recurring_wins: tuple[PatternEvidence, ...] = ()
    anti_patterns: tuple[AntiPatternRecord, ...] = ()
    trends: MemoryTrendSnapshot | None = None
    last_feedback: dict[str, Any] = field(default_factory=dict)
    last_run: BusinessMemoryRunRecord | None = None
    recent_runs: tuple[BusinessMemoryRunRecord, ...] = ()
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    average_goal_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "business_profile": dict(self.business_profile),
            "active_goals": list(self.active_goals),
            "operating_constraints": dict(self.operating_constraints),
            "learned_preferences": dict(self.learned_preferences),
            "signal_memory": [asdict(item) for item in self.signal_memory],
            "recurring_failures": [asdict(item) for item in self.recurring_failures],
            "recurring_wins": [asdict(item) for item in self.recurring_wins],
            "anti_patterns": [asdict(item) for item in self.anti_patterns],
            "trends": None if self.trends is None else asdict(self.trends),
            "last_feedback": dict(self.last_feedback),
            "last_run": None if self.last_run is None else asdict(self.last_run),
            "recent_runs": [asdict(item) for item in self.recent_runs],
            "total_runs": int(self.total_runs),
            "completed_runs": int(self.completed_runs),
            "failed_runs": int(self.failed_runs),
            "average_goal_score": float(self.average_goal_score),
        }

    def to_evidence_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "business_profile": dict(self.business_profile),
            "aggregated_business_profile": dict(self.business_profile),
            "active_goals": list(self.active_goals),
            "operating_constraints": dict(self.operating_constraints),
            "learned_preferences": dict(self.learned_preferences),
            "signal_memory": [asdict(item) for item in self.signal_memory],
            "recurring_failures": self._sorted_evidence_patterns(self.recurring_failures),
            "recurring_wins": self._sorted_evidence_patterns(self.recurring_wins),
            "anti_patterns": self._sorted_evidence_anti_patterns(self.anti_patterns),
            "trends": {} if self.trends is None else asdict(self.trends),
            "last_feedback": dict(self.last_feedback),
            "last_run": None if self.last_run is None else asdict(self.last_run),
            "recent_runs": [asdict(item) for item in self.recent_runs],
            "total_runs": int(self.total_runs),
            "completed_runs": int(self.completed_runs),
            "failed_runs": int(self.failed_runs),
            "average_goal_score": float(self.average_goal_score),
            "evidence_only": True,
            "must_not_issue_decision": True,
            "must_not_unlock_effects": True,
        }

    def to_summary_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "business_profile": dict(self.business_profile),
            "total_runs": int(self.total_runs),
            "completed_runs": int(self.completed_runs),
            "failed_runs": int(self.failed_runs),
            "average_goal_score": float(self.average_goal_score),
            "active_goals": list(self.active_goals),
            "learned_preferences": dict(self.learned_preferences),
            "operating_constraints": dict(self.operating_constraints),
            "recurring_failures": sorted(item.key for item in self.recurring_failures),
            "recurring_wins": sorted(item.key for item in self.recurring_wins),
            "anti_patterns": sorted(item.key for item in self.anti_patterns),
            "trends": {} if self.trends is None else asdict(self.trends),
            "evidence_only": True,
            "must_not_issue_decision": True,
            "must_not_unlock_effects": True,
        }

    def to_state_context_payload(self, *, policy: BusinessMemoryPolicy | None = None) -> dict[str, Any]:
        canonical_policy = policy or BusinessMemoryPolicy()
        evidence = self.to_evidence_payload()
        aggregated_profile = canonical_policy.sanitize_feedback_payload(
            dict(evidence.get("aggregated_business_profile") or evidence.get("business_profile") or {})
        )
        recurring_failures = self._sorted_state_patterns(self.recurring_failures)
        recurring_wins = self._sorted_state_patterns(self.recurring_wins)
        anti_patterns = self._sorted_state_anti_patterns(self.anti_patterns)
        return {
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "recurring_failures": recurring_failures,
            "recurring_wins": recurring_wins,
            "anti_patterns": anti_patterns,
            "trends": {} if self.trends is None else asdict(self.trends),
            "learned_preferences": canonical_policy.sanitize_feedback_payload(dict(self.learned_preferences)),
            "active_goals": sorted(str(item) for item in self.active_goals if str(item).strip()),
            "operating_constraints": canonical_policy.sanitize_feedback_payload(dict(self.operating_constraints)),
            "aggregated_business_profile": aggregated_profile,
            "total_runs": int(self.total_runs),
            "completed_runs": int(self.completed_runs),
            "failed_runs": int(self.failed_runs),
            "average_goal_score": float(self.average_goal_score),
            "evidence_only": True,
            "must_not_issue_decision": True,
            "must_not_unlock_effects": True,
        }

    @staticmethod
    def _sorted_evidence_patterns(items: tuple[PatternEvidence, ...]) -> list[dict[str, Any]]:
        return [
            asdict(item)
            for item in sorted(
                items,
                key=lambda current: (
                    str(current.key),
                    -float(current.confidence),
                    -float(current.frequency),
                    -float(current.freshness),
                    -int(current.count),
                ),
            )
        ]

    @staticmethod
    def _sorted_evidence_anti_patterns(items: tuple[AntiPatternRecord, ...]) -> list[dict[str, Any]]:
        return [
            asdict(item)
            for item in sorted(
                items,
                key=lambda current: (
                    str(current.key),
                    -float(current.confidence),
                    -float(current.frequency),
                    -float(current.freshness),
                ),
            )
        ]

    @staticmethod
    def _state_pattern_payload(item: PatternEvidence) -> dict[str, Any]:
        payload = asdict(item)
        if payload.get("key"):
            payload.setdefault("action", str(payload["key"]))
        return payload

    @staticmethod
    def _state_anti_pattern_payload(item: AntiPatternRecord) -> dict[str, Any]:
        payload = asdict(item)
        if payload.get("key"):
            payload.setdefault("action", str(payload["key"]))
        return payload

    @classmethod
    def _sorted_state_patterns(cls, items: tuple[PatternEvidence, ...]) -> list[dict[str, Any]]:
        ordered = sorted(
            items,
            key=lambda item: (-int(item.count), -float(item.frequency), -float(item.confidence), str(item.key)),
        )
        return [cls._state_pattern_payload(item) for item in ordered]

    @classmethod
    def _sorted_state_anti_patterns(cls, items: tuple[AntiPatternRecord, ...]) -> list[dict[str, Any]]:
        ordered = sorted(
            items,
            key=lambda item: (-float(item.confidence), -float(item.frequency), -float(item.freshness), str(item.key)),
        )
        return [cls._state_anti_pattern_payload(item) for item in ordered]

    @classmethod
    def empty(cls, *, tenant_id: str, business_id: str) -> BusinessOperatingMemory:
        return cls(
            schema_version=BUSINESS_MEMORY_SCHEMA_VERSION,
            tenant_id=_text(tenant_id),
            business_id=_text(business_id),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, policy: BusinessMemoryPolicy | None = None) -> BusinessOperatingMemory:
        canonical_policy = policy or BusinessMemoryPolicy()
        migrated = _migrate_business_memory_payload(payload, policy=canonical_policy)
        raw_last_run = migrated.get("last_run")
        raw_recent_runs = migrated.get("recent_runs") or []
        raw_signals = migrated.get("signal_memory") or []
        raw_failures = migrated.get("recurring_failures") or []
        raw_wins = migrated.get("recurring_wins") or []
        raw_anti = migrated.get("anti_patterns") or []
        raw_trends = migrated.get("trends")
        recent_runs = _dedupe_recent_runs(tuple(_run_record_from_row(row, policy=canonical_policy) for row in raw_recent_runs if isinstance(row, Mapping)))
        signal_memory = tuple(_signal_record_from_row(row, policy=canonical_policy) for row in raw_signals if isinstance(row, Mapping))
        recurring_failures = tuple(_pattern_from_row(row, policy=canonical_policy) for row in raw_failures if isinstance(row, Mapping))
        recurring_wins = tuple(_pattern_from_row(row, policy=canonical_policy) for row in raw_wins if isinstance(row, Mapping))
        anti_patterns = tuple(_anti_pattern_from_row(row, policy=canonical_policy) for row in raw_anti if isinstance(row, Mapping))
        trends = _trend_from_row(raw_trends, policy=canonical_policy) if isinstance(raw_trends, Mapping) else None
        last_run = _run_record_from_row(raw_last_run, policy=canonical_policy) if isinstance(raw_last_run, Mapping) else None
        memory = cls(
            schema_version=BUSINESS_MEMORY_SCHEMA_VERSION,
            tenant_id=canonical_policy.sanitize_text(migrated.get("tenant_id"), max_length=128),
            business_id=canonical_policy.sanitize_text(migrated.get("business_id"), max_length=128),
            business_profile=canonical_policy.sanitize_mapping(migrated.get("business_profile"), limit=canonical_policy.max_profile_fields),
            active_goals=canonical_policy.sanitize_goal_list(list(migrated.get("active_goals") or [])),
            operating_constraints=canonical_policy.sanitize_mapping(migrated.get("operating_constraints"), limit=canonical_policy.max_constraint_fields),
            learned_preferences=canonical_policy.sanitize_mapping(migrated.get("learned_preferences"), limit=canonical_policy.max_preferences),
            signal_memory=signal_memory,
            recurring_failures=recurring_failures,
            recurring_wins=recurring_wins,
            anti_patterns=anti_patterns,
            trends=trends,
            last_feedback=canonical_policy.sanitize_feedback_payload(migrated.get("last_feedback") or {}),
            last_run=last_run,
            recent_runs=recent_runs,
            total_runs=canonical_policy.clamp_non_negative_int(migrated.get("total_runs")),
            completed_runs=canonical_policy.clamp_non_negative_int(migrated.get("completed_runs")),
            failed_runs=canonical_policy.clamp_non_negative_int(migrated.get("failed_runs")),
            average_goal_score=canonical_policy.clamp_goal_score(migrated.get("average_goal_score")),
        )
        return _reconcile_memory_invariants(memory, policy=canonical_policy)

def _dedupe_recent_runs(rows: tuple[BusinessMemoryRunRecord, ...]) -> tuple[BusinessMemoryRunRecord, ...]:
    return _dedupe_recent_runs_owner(rows)

def _reconcile_memory_invariants(memory: BusinessOperatingMemory, *, policy: BusinessMemoryPolicy) -> BusinessOperatingMemory:
    recent_runs = _dedupe_recent_runs(tuple(memory.recent_runs))
    minimum_total = max(len(recent_runs), int(memory.completed_runs) + int(memory.failed_runs))
    total_runs = max(int(memory.total_runs), minimum_total)
    completed_runs = max(0, min(int(memory.completed_runs), total_runs))
    failed_runs = max(0, min(int(memory.failed_runs), total_runs - completed_runs))
    if completed_runs + failed_runs < minimum_total:
        failed_runs = min(total_runs - completed_runs, minimum_total - completed_runs)
    average_goal_score = 0.0 if total_runs <= 0 else policy.clamp_goal_score(memory.average_goal_score)
    return BusinessOperatingMemory(
        schema_version=int(memory.schema_version),
        tenant_id=policy.sanitize_text(memory.tenant_id, max_length=128),
        business_id=policy.sanitize_text(memory.business_id, max_length=128),
        business_profile=policy.sanitize_mapping(memory.business_profile, limit=policy.max_profile_fields),
        active_goals=policy.sanitize_goal_list(memory.active_goals),
        operating_constraints=policy.sanitize_mapping(memory.operating_constraints, limit=policy.max_constraint_fields),
        learned_preferences=policy.sanitize_mapping(memory.learned_preferences, limit=policy.max_preferences),
        signal_memory=tuple(memory.signal_memory[: int(policy.max_signals)]),
        recurring_failures=tuple(memory.recurring_failures[: int(policy.max_failures)]),
        recurring_wins=tuple(memory.recurring_wins[: int(policy.max_wins)]),
        anti_patterns=tuple(memory.anti_patterns[: int(policy.max_anti_patterns)]),
        trends=memory.trends,
        last_feedback=policy.sanitize_feedback_payload(memory.last_feedback),
        last_run=memory.last_run,
        recent_runs=recent_runs[: int(policy.max_recent_runs)],
        total_runs=total_runs,
        completed_runs=completed_runs,
        failed_runs=failed_runs,
        average_goal_score=average_goal_score,
    )

def _signal_record_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> SignalMemoryRecord:
    return _signal_record_from_row_owner(row, policy=policy)

def _pattern_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> PatternEvidence:
    return _pattern_from_row_owner(row, policy=policy)

def _anti_pattern_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> AntiPatternRecord:
    return _anti_pattern_from_row_owner(row, policy=policy)

def _run_record_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> BusinessMemoryRunRecord:
    return _run_record_from_row_owner(row, policy=policy)

def _trend_from_row(row: Mapping[str, Any], *, policy: BusinessMemoryPolicy) -> MemoryTrendSnapshot:
    return _trend_from_row_owner(row, policy=policy)

def _migrate_business_memory_payload(payload: dict[str, Any], *, policy: BusinessMemoryPolicy) -> dict[str, Any]:
    return _migrate_business_memory_payload_owner(payload, policy=policy)

def project_business_memory_meta_payloads(
    payload: Mapping[str, Any] | None,
    *,
    policy: BusinessMemoryPolicy | None = None,
    recent_runs_limit: int = 10,
) -> dict[str, dict[str, Any]]:
    bundle = project_business_memory_contract_bundle(payload, policy=policy, recent_runs_limit=recent_runs_limit)
    return {
        "business_memory": dict(bundle.get("evidence") or {}),
        "business_memory_evidence": dict(bundle.get("state_context") or {}),
        "business_memory_summary": dict(bundle.get("governance_summary") or {}),
    }

@dataclass
class FileBusinessOperatingMemoryStore:
    root_dir: Path
    policy: BusinessMemoryPolicy = field(default_factory=BusinessMemoryPolicy)
    compactor: object | None = None
    taxonomy: BusinessMemoryTaxonomy = field(default_factory=BusinessMemoryTaxonomy)
    matcher: BusinessMemoryMatcher = field(default_factory=BusinessMemoryMatcher)

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        if self.compactor is None:
            from application.memory.business_memory_compactor import BusinessMemoryCompactor

            self.compactor = BusinessMemoryCompactor(policy=self.policy)

    def load(self, *, tenant_id: str, business_id: str) -> BusinessOperatingMemory:
        path = self._target_path(tenant_id=tenant_id, business_id=business_id)
        if not path.exists():
            return BusinessOperatingMemory.empty(tenant_id=tenant_id, business_id=business_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return BusinessOperatingMemory.empty(tenant_id=tenant_id, business_id=business_id)
        memory = BusinessOperatingMemory.from_dict(payload, policy=self.policy)
        return self.compactor.compact(memory) if self.compactor is not None else memory

    def save(self, memory: BusinessOperatingMemory) -> Path:
        target = self._target_path(tenant_id=memory.tenant_id, business_id=memory.business_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        compacted = self.compactor.compact(memory) if self.compactor is not None else memory
        payload = json.dumps(compacted.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        with FileBusinessMemoryLock(
            target_path=target,
            timeout_seconds=float(self.policy.save_lock_timeout_seconds),
            retry_delay_seconds=float(self.policy.save_lock_retry_delay_seconds),
        ):
            fd, temp_name = tempfile.mkstemp(prefix=".business_memory_", suffix=".json", dir=str(target.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, target)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        return target

    def list_businesses(self, *, tenant_id: str | None = None) -> tuple[tuple[str, str], ...]:
        if tenant_id is not None:
            files = sorted((self.root_dir / _safe_key(tenant_id, fallback="default")).glob("*.json"))
        else:
            files = sorted(self.root_dir.glob("*/*.json"))
        result: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in files:
            try:
                payload = json.loads(item.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            key = (_text(payload.get("tenant_id")), _text(payload.get("business_id")))
            if key in seen or not all(key):
                continue
            seen.add(key)
            result.append(key)
        return tuple(result)

    def remember_execution(
        self,
        *,
        tenant_id: str,
        business_id: str,
        run_id: str,
        goal: str,
        completed: bool,
        stop_reason: str,
        final_feedback: dict[str, Any],
        step_count: int,
        profile: dict[str, Any],
        constraints: dict[str, Any],
        signals: list[dict[str, Any]],
        meta: dict[str, Any],
        channel: str,
        region: str,
        product_name: str,
        recorded_at: str | None = None,
        canonical_run_artifact: dict[str, Any] | None = None,
    ) -> BusinessOperatingMemory:
        current = self.load(tenant_id=tenant_id, business_id=business_id)
        canonical_memory = canonical_memory_record(
            tenant_id=tenant_id,
            business_id=business_id,
            run_id=run_id,
            goal=goal,
            step_count=_safe_int(step_count),
            final_feedback=dict(final_feedback or {}),
            canonical_run_artifact=dict(canonical_run_artifact or {}),
            channel=channel,
            region=region,
            completed=bool(completed),
            stop_reason=stop_reason,
        )
        goal_score = _safe_float(canonical_memory.get("goal_score"))
        feedback_payload = dict(final_feedback or {})
        feedback_payload.setdefault("persistence_vocabulary", dict(canonical_memory.get("persistence_vocabulary") or {}))
        feedback_payload.setdefault(
            "verification_status",
            str(canonical_memory.get("verification_status") or feedback_payload.get("verification_status") or "unknown"),
        )
        feedback_payload = self.policy.sanitize_feedback_payload(feedback_payload)

        fingerprint = self.matcher.build_fingerprint(
            goal=goal,
            profile=dict(profile or {}),
            meta=dict(meta or {}),
            channel=channel,
            region=region,
        )
        normalized = self.taxonomy.normalize_feedback(
            completed=completed,
            stop_reason=stop_reason,
            final_feedback=feedback_payload,
        )
        run_record = BusinessMemoryRunRecord(
            run_id=self.policy.sanitize_text(run_id, max_length=128),
            goal=self.policy.sanitize_text(goal, max_length=self.policy.max_summary_length),
            completed=bool(completed),
            stop_reason=self.policy.sanitize_text(stop_reason, max_length=96),
            goal_score=float(goal_score),
            step_count=self.policy.clamp_non_negative_int(step_count),
            summary=self._build_run_summary(
                goal=goal,
                completed=completed,
                stop_reason=stop_reason,
                final_feedback=feedback_payload,
                normalized_failure_kind=normalized.failure_kind,
                normalized_outcomes=normalized.outcome_kinds,
            ),
            channel=self.policy.sanitize_text(channel, max_length=96),
            region=self.policy.sanitize_text(region, max_length=96),
            product_name=self.policy.sanitize_text(product_name, max_length=128),
            goal_family=fingerprint.goal_family,
            fingerprint=self.policy.sanitize_mapping(fingerprint.to_dict(), limit=12, value_max_length=96),
            recorded_at=self.policy.sanitize_text(recorded_at, max_length=64) or None,
        )

        replay_run_id = run_record.run_id if run_record.run_id and run_record.run_id in {row.run_id for row in current.recent_runs} else None
        previous_run = next((row for row in current.recent_runs if row.run_id == replay_run_id), None)

        total_runs = int(current.total_runs) if replay_run_id else int(current.total_runs) + 1
        completed_runs = self._next_completed_runs(current=current, replay=previous_run, now_completed=completed)
        failed_runs = self._next_failed_runs(current=current, replay=previous_run, now_completed=completed)

        existing_failures = self._remove_run_from_patterns(current.recurring_failures, replay_run_id=replay_run_id, total_runs=total_runs)
        existing_wins = self._remove_run_from_patterns(current.recurring_wins, replay_run_id=replay_run_id, total_runs=total_runs)

        updated = BusinessOperatingMemory(
            schema_version=BUSINESS_MEMORY_SCHEMA_VERSION,
            tenant_id=self.policy.sanitize_text(tenant_id, max_length=128),
            business_id=self.policy.sanitize_text(business_id, max_length=128),
            business_profile=self._merge_profile(current=current, profile=profile, meta=meta),
            active_goals=tuple(self._merge_active_goals(current=current, goal=goal)),
            operating_constraints=self._merge_constraints(current=current, constraints=constraints),
            learned_preferences=self._merge_preferences(current=current, profile=profile, meta=meta),
            signal_memory=tuple(self._merge_signals(current=current, signals=signals, run_id=run_id, recorded_at=recorded_at, replay_run_id=replay_run_id)),
            recurring_failures=tuple(
                self._merge_patterns(
                    existing=tuple(existing_failures),
                    keys=self._failure_keys(normalized_feedback=normalized),
                    total_runs=total_runs,
                    run_id=run_id,
                    recorded_at=recorded_at,
                )
            ),
            recurring_wins=tuple(
                self._merge_patterns(
                    existing=tuple(existing_wins),
                    keys=self._win_keys(normalized_feedback=normalized),
                    total_runs=total_runs,
                    run_id=run_id,
                    recorded_at=recorded_at,
                )
            ),
            anti_patterns=(),
            trends=None,
            last_feedback=dict(feedback_payload),
            last_run=run_record,
            recent_runs=tuple(self._merge_recent_runs(current=current, new_record=run_record)),
            total_runs=total_runs,
            completed_runs=completed_runs,
            failed_runs=failed_runs,
            average_goal_score=self._next_average(
                current_average=float(current.average_goal_score),
                current_total=int(current.total_runs),
                new_score=float(goal_score),
                replay_previous_score=None if previous_run is None else float(previous_run.goal_score),
            ),
        )

        updated = self.compactor.compact(updated) if self.compactor is not None else updated
        self.save(updated)
        return self.load(tenant_id=tenant_id, business_id=business_id)

    def _target_path(self, *, tenant_id: str, business_id: str) -> Path:
        return self.root_dir / _safe_key(tenant_id, fallback="default") / f"{_safe_key(business_id, fallback='business')}.json"

    def _merge_recent_runs(
        self,
        *,
        current: BusinessOperatingMemory,
        new_record: BusinessMemoryRunRecord,
    ) -> list[BusinessMemoryRunRecord]:
        rows = [new_record]
        rows.extend([row for row in current.recent_runs if row.run_id != new_record.run_id])
        return rows[: int(self.policy.max_recent_runs)]

    def _merge_profile(self, *, current: BusinessOperatingMemory, profile: dict[str, Any], meta: dict[str, Any]) -> dict[str, str]:
        merged = dict(current.business_profile)
        sanitized_profile = self.policy.sanitize_mapping(dict(profile or {}), limit=self.policy.max_profile_fields)
        sanitized_meta = self.policy.sanitize_mapping(
            {k: v for k, v in dict(meta or {}).items() if k in {"channel", "region", "traffic_source", "offer_type"}},
            limit=self.policy.max_profile_fields,
        )
        merged.update({key: value for key, value in sanitized_profile.items() if value})
        merged.update({key: value for key, value in sanitized_meta.items() if value})
        return self.policy.sanitize_mapping(merged, limit=self.policy.max_profile_fields)

    def _merge_constraints(self, *, current: BusinessOperatingMemory, constraints: dict[str, Any]) -> dict[str, str]:
        merged = dict(current.operating_constraints)
        merged.update(self.policy.sanitize_mapping(dict(constraints or {}), limit=self.policy.max_constraint_fields))
        return self.policy.sanitize_mapping(merged, limit=self.policy.max_constraint_fields)

    def _merge_preferences(self, *, current: BusinessOperatingMemory, profile: dict[str, Any], meta: dict[str, Any]) -> dict[str, str]:
        payload: dict[str, Any] = {}
        sources = (dict(profile or {}), dict(meta or {}))
        for key in ("segment", "offer_type", "traffic_source", "preferred_channel", "channel", "region"):
            value = None
            for source in sources:
                value = source.get(key)
                if value is not None:
                    break
            if value is not None:
                payload[key] = value
        merged = dict(current.learned_preferences)
        merged.update(self.policy.sanitize_mapping(payload, limit=self.policy.max_preferences))
        if "preferred_channel" in merged and "channel" not in merged:
            merged["channel"] = merged["preferred_channel"]
        return self.policy.sanitize_mapping(merged, limit=self.policy.max_preferences)

    def _merge_active_goals(self, *, current: BusinessOperatingMemory, goal: str) -> list[str]:
        values = [self.policy.sanitize_text(goal, max_length=self.policy.max_summary_length)]
        if not _text(goal).casefold().startswith("done:"):
            values.extend(list(current.active_goals))
        return _dedupe(values)[: int(self.policy.max_active_goals)]

    def _merge_signals(
        self,
        *,
        current: BusinessOperatingMemory,
        signals: list[dict[str, Any]],
        run_id: str,
        recorded_at: str | None,
        replay_run_id: str | None,
    ) -> list[SignalMemoryRecord]:
        index = {item.key(): item for item in current.signal_memory}
        touched: set[str] = set()
        for raw in list(signals or []):
            if not isinstance(raw, dict):
                continue
            kind = self.policy.sanitize_text(raw.get("kind") or raw.get("type") or "signal", max_length=64)
            name = self.policy.sanitize_text(raw.get("name") or raw.get("key") or "signal", max_length=128)
            last_value = self.policy.sanitize_text(raw.get("value") or raw.get("last_value") or name, max_length=160)
            marker = f"{kind}::{name}"
            previous = index.get(marker)
            is_replay_marker = replay_run_id is not None and previous is not None and previous.last_seen_run_id == replay_run_id
            count = 1 if previous is None else int(previous.count) + (0 if marker in touched or is_replay_marker else 1)
            touched.add(marker)
            trend = self.policy.sanitize_text(raw.get("trend") or (previous.trend if previous else "unknown"), max_length=32) or "unknown"
            index[marker] = SignalMemoryRecord(
                kind=kind,
                name=name,
                last_value=last_value,
                count=max(1, count),
                last_seen_run_id=self.policy.sanitize_text(run_id, max_length=128) or None,
                last_seen_at=self.policy.sanitize_text(recorded_at, max_length=64) or None,
                trend=trend,
            )
        return sorted(index.values(), key=lambda item: (-int(item.count), item.kind, item.name))[: int(self.policy.max_signals)]

    def _merge_patterns(
        self,
        *,
        existing: tuple[PatternEvidence, ...],
        keys: list[str],
        total_runs: int,
        run_id: str,
        recorded_at: str | None,
    ) -> list[PatternEvidence]:
        index = {item.key: item for item in existing}
        for raw_key in _dedupe(keys):
            stable_key = self.policy.sanitize_text(raw_key, max_length=128)
            if not stable_key:
                continue
            previous = index.get(stable_key)
            count = 1 if previous is None else int(previous.count) + 1
            frequency = float(count) / float(max(total_runs, 1))
            freshness = 1.0
            confidence = self._pattern_confidence(previous=previous, count=count, frequency=frequency)
            index[stable_key] = PatternEvidence(
                key=stable_key,
                count=count,
                last_seen_run_id=self.policy.sanitize_text(run_id, max_length=128) or None,
                last_seen_at=self.policy.sanitize_text(recorded_at, max_length=64) or None,
                confidence=self.policy.normalize_confidence(confidence),
                frequency=self.policy.normalize_frequency(frequency),
                freshness=self.policy.normalize_unit_interval(freshness),
                source_run_ids=self._merge_source_run_ids(previous=previous, run_id=run_id),
            )
        return sorted(index.values(), key=lambda item: (-int(item.count), -float(item.frequency), item.key))

    def _remove_run_from_patterns(
        self,
        patterns: tuple[PatternEvidence, ...],
        *,
        replay_run_id: str | None,
        total_runs: int,
    ) -> list[PatternEvidence]:
        if not replay_run_id:
            return list(patterns)
        result: list[PatternEvidence] = []
        for item in patterns:
            if replay_run_id not in item.source_run_ids and replay_run_id != item.last_seen_run_id:
                result.append(item)
                continue
            remaining_run_ids = [rid for rid in item.source_run_ids if rid != replay_run_id]
            new_count = max(0, int(item.count) - 1)
            if new_count <= 0:
                continue
            result.append(
                PatternEvidence(
                    key=item.key,
                    count=new_count,
                    last_seen_run_id=item.last_seen_run_id if item.last_seen_run_id != replay_run_id else (remaining_run_ids[0] if remaining_run_ids else None),
                    last_seen_at=item.last_seen_at if item.last_seen_run_id != replay_run_id else None,
                    confidence=self._pattern_confidence(previous=None, count=new_count, frequency=float(new_count) / float(max(total_runs, 1))),
                    frequency=self.policy.normalize_frequency(float(new_count) / float(max(total_runs, 1))),
                    freshness=self.policy.normalize_unit_interval(min(float(item.freshness), self.policy.estimate_half_life_decay(age_in_runs=1))),
                    source_run_ids=tuple(remaining_run_ids[: int(self.policy.max_source_run_ids)]),
                )
            )
        return result

    def _merge_source_run_ids(self, *, previous: PatternEvidence | None, run_id: str) -> tuple[str, ...]:
        items = [self.policy.sanitize_text(run_id, max_length=128)]
        if previous is not None:
            items.extend(list(previous.source_run_ids))
        return tuple(_dedupe(items)[: int(self.policy.max_source_run_ids)])

    def _pattern_confidence(self, *, previous: PatternEvidence | None, count: int, frequency: float) -> float:
        baseline = 0.25 + (0.12 * float(count)) + (0.20 * float(frequency))
        if previous is not None:
            baseline = max(float(previous.confidence), baseline)
        return self.policy.normalize_confidence(min(0.95, baseline))

    def _failure_keys(self, *, normalized_feedback: NormalizedFeedback) -> list[str]:
        if not normalized_feedback.failure_kind:
            return []
        kind = "timeout" if normalized_feedback.failure_kind == "timeout_external" else normalized_feedback.failure_kind
        return [kind]

    def _win_keys(self, *, normalized_feedback: NormalizedFeedback) -> list[str]:
        return [item for item in normalized_feedback.outcome_kinds]

    def _next_average(
        self,
        *,
        current_average: float,
        current_total: int,
        new_score: float,
        replay_previous_score: float | None,
    ) -> float:
        if replay_previous_score is not None and current_total > 0:
            adjusted_sum = (float(current_average) * float(current_total)) - float(replay_previous_score) + float(new_score)
            return adjusted_sum / float(current_total)
        if current_total <= 0:
            return float(new_score)
        return ((float(current_average) * float(current_total)) + float(new_score)) / float(current_total + 1)

    def _next_completed_runs(self, *, current: BusinessOperatingMemory, replay: BusinessMemoryRunRecord | None, now_completed: bool) -> int:
        if replay is None:
            return int(current.completed_runs) + (1 if now_completed else 0)
        return max(0, int(current.completed_runs) - (1 if replay.completed else 0) + (1 if now_completed else 0))

    def _next_failed_runs(self, *, current: BusinessOperatingMemory, replay: BusinessMemoryRunRecord | None, now_completed: bool) -> int:
        if replay is None:
            return int(current.failed_runs) + (0 if now_completed else 1)
        return max(0, int(current.failed_runs) - (0 if replay.completed else 1) + (0 if now_completed else 1))

    def _build_run_summary(
        self,
        *,
        goal: str,
        completed: bool,
        stop_reason: str,
        final_feedback: dict[str, Any],
        normalized_failure_kind: str | None,
        normalized_outcomes: list[str],
    ) -> str:
        parts = [self.policy.sanitize_text(goal, max_length=160)]
        if completed:
            parts.append("completed")
        else:
            parts.append(self.policy.sanitize_text(stop_reason or "failed", max_length=64))
        if normalized_failure_kind:
            parts.append(self.policy.sanitize_text(normalized_failure_kind, max_length=64))
        elif normalized_outcomes:
            parts.append(self.policy.sanitize_text(normalized_outcomes[0], max_length=64))
        elif final_feedback.get("error"):
            parts.append(self.policy.sanitize_text(final_feedback.get("error"), max_length=64))
        return " | ".join(part for part in parts if part)

__all__ = [
    "BUSINESS_MEMORY_SCHEMA_VERSION",
    "BusinessMemoryCompactor",
    "BusinessMemoryPolicy",
    "BusinessOperatingMemory",
    "CANON_PERSISTENT_BUSINESS_OPERATING_MEMORY",
    "FileBusinessOperatingMemoryStore",
    "canonicalize_business_memory_payload",
    "project_business_memory_evidence",
    "project_business_memory_patterns",
    "project_business_memory_profile",
    "project_business_memory_recent_runs",
    "project_business_memory_state_context",
    "project_business_memory_contract_bundle",
    "project_business_memory_meta_payloads",
    "project_business_memory_feedback_snapshot",
    "project_business_memory_summary",
    "project_business_memory_governance_summary",
]
