from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from math import ceil

from .contracts import (
    AutomationOpportunity,
    DiscoveryPolicy,
    DiscoveryReport,
    MoneyStatus,
    ProcessBaseline,
    ProcessObservation,
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _stable_id(*parts: object, prefix: str) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _observation_fingerprint(item: ProcessObservation) -> str:
    payload = {
        "tenant_id": item.tenant_id,
        "business_id": item.business_id,
        "process_key": item.process_key,
        "occurred_at": item.occurred_at.isoformat(),
        "source": item.source,
        "evidence_id": item.evidence_id,
        "manual_minutes": item.manual_minutes,
        "actor_cost_per_hour_minor": item.actor_cost_per_hour_minor,
        "direct_loss_minor": item.direct_loss_minor,
        "revenue_at_risk_minor": item.revenue_at_risk_minor,
        "currency": item.currency,
        "automation_fit": float(item.automation_fit),
        "operational_risk": float(item.operational_risk),
        "trust_weight": float(item.trust_weight),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dedupe_observations(observations: Sequence[ProcessObservation]) -> tuple[ProcessObservation, ...]:
    by_id: dict[str, tuple[str, ProcessObservation]] = {}
    for item in observations:
        fingerprint = _observation_fingerprint(item)
        existing = by_id.get(item.evidence_id)
        if existing is None:
            by_id[item.evidence_id] = (fingerprint, item)
            continue
        if existing[0] != fingerprint:
            raise ValueError("conflicting observations share one evidence_id")
    return tuple(value[1] for value in by_id.values())


def _evidence_fingerprint(observations: Sequence[ProcessObservation]) -> str:
    parts = sorted(f"{item.evidence_id}:{_observation_fingerprint(item)}" for item in observations)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _window_days(observations: Sequence[ProcessObservation]) -> int:
    start = min(item.occurred_at for item in observations)
    end = max(item.occurred_at for item in observations)
    return max(1, ceil((end - start).total_seconds() / 86400) + 1)


def _normalize_30d(value: float, *, window_days: int) -> float:
    return value * 30.0 / max(1, window_days)


def _money_status(observations: Sequence[ProcessObservation]) -> tuple[MoneyStatus, str | None]:
    currencies = {item.currency for item in observations if item.currency}
    if len(currencies) > 1:
        return MoneyStatus.MIXED_CURRENCY, None
    currency = next(iter(currencies), None)
    any_money = any(
        item.actor_cost_per_hour_minor is not None
        or item.direct_loss_minor is not None
        or item.revenue_at_risk_minor is not None
        for item in observations
    )
    if not any_money:
        return MoneyStatus.UNAVAILABLE, None
    trusted_money_sources = all(item.source != "owner_asserted" for item in observations)
    if currency and trusted_money_sources and all(item.realized_money_complete for item in observations):
        return MoneyStatus.VERIFIED, currency
    return MoneyStatus.PARTIAL, currency


def aggregate_baseline(observations: Sequence[ProcessObservation], policy: DiscoveryPolicy) -> ProcessBaseline:
    if not observations:
        raise ValueError("cannot aggregate an empty process")
    unique = _dedupe_observations(tuple(observations))
    scopes = {(item.tenant_id, item.business_id, item.process_key) for item in unique}
    if len(scopes) != 1:
        raise ValueError("baseline input must be one tenant/business/process")
    ordered = sorted(unique, key=lambda item: (item.occurred_at, item.evidence_id))
    start = ordered[0].occurred_at
    end = ordered[-1].occurred_at
    window_days = _window_days(ordered)
    sources = {item.source for item in ordered}
    occurrences = _normalize_30d(len(ordered), window_days=window_days)
    manual_minutes = round(_normalize_30d(sum(item.manual_minutes for item in ordered), window_days=window_days))
    automation_fit = sum(item.automation_fit for item in ordered) / len(ordered)
    operational_risk = sum(item.operational_risk for item in ordered) / len(ordered)

    money_status, currency = _money_status(ordered)
    realized_loss: int | None = None
    if money_status is MoneyStatus.VERIFIED:
        realized_values = [item.realized_cost_minor for item in ordered]
        assert all(value is not None for value in realized_values)
        realized_loss = round(_normalize_30d(sum(int(value) for value in realized_values), window_days=window_days))

    risk_values = [item.revenue_at_risk_minor for item in ordered]
    revenue_at_risk: int | None = None
    if currency and all(value is not None for value in risk_values):
        revenue_at_risk = round(
            _normalize_30d(sum(int(value) for value in risk_values if value is not None), window_days=window_days)
        )

    sample_factor = _clamp(len(ordered) / policy.reference_observations)
    window_factor = _clamp(window_days / policy.reference_window_days)
    source_factor = _clamp(len(sources) / 2.0)
    trust_factor = _clamp(sum(item.trust_weight for item in ordered) / len(ordered))
    confidence = round(0.35 * sample_factor + 0.30 * window_factor + 0.15 * source_factor + 0.20 * trust_factor, 4)

    refs = tuple(item.evidence_id for item in ordered)
    return ProcessBaseline(
        tenant_id=ordered[0].tenant_id,
        business_id=ordered[0].business_id,
        process_key=ordered[0].process_key,
        window_start=start,
        window_end=end,
        window_days=window_days,
        observation_count=len(ordered),
        source_count=len(sources),
        occurrences_per_30d=round(occurrences, 3),
        manual_minutes_per_30d=manual_minutes,
        realized_loss_minor_per_30d=realized_loss,
        revenue_at_risk_minor_per_30d=revenue_at_risk,
        currency=currency,
        money_status=money_status,
        average_automation_fit=round(_clamp(automation_fit), 4),
        average_operational_risk=round(_clamp(operational_risk), 4),
        confidence=confidence,
        evidence_refs=refs,
        evidence_fingerprint=_evidence_fingerprint(ordered),
    )


def _priority_score(baseline: ProcessBaseline, policy: DiscoveryPolicy) -> float:
    time_denominator = max(1, policy.min_manual_minutes_per_30d)
    time_impact = _clamp(baseline.manual_minutes_per_30d / time_denominator)
    money_impact = 0.0
    if baseline.realized_loss_minor_per_30d is not None:
        if policy.min_realized_loss_minor_per_30d > 0:
            money_impact = _clamp(baseline.realized_loss_minor_per_30d / policy.min_realized_loss_minor_per_30d)
        elif baseline.realized_loss_minor_per_30d > 0:
            money_impact = 1.0
    impact = max(time_impact, money_impact)
    frequency = _clamp(baseline.occurrences_per_30d / policy.reference_occurrences_per_30d)
    raw = 0.35 * impact + 0.20 * frequency + 0.25 * baseline.confidence + 0.20 * baseline.average_automation_fit
    risk_discount = 1.0 - 0.65 * baseline.average_operational_risk
    return round(100.0 * _clamp(raw * risk_discount), 2)


def evaluate_opportunity(baseline: ProcessBaseline, policy: DiscoveryPolicy) -> AutomationOpportunity:
    blockers: list[str] = []
    reasons: list[str] = []
    if baseline.observation_count < policy.min_observations:
        blockers.append("insufficient_observation_count")
    if baseline.window_days < policy.min_window_days:
        blockers.append("insufficient_observation_window")
    if baseline.confidence < policy.min_confidence:
        blockers.append("insufficient_confidence")
    if baseline.average_automation_fit < policy.min_automation_fit:
        blockers.append("automation_fit_below_threshold")
    if baseline.average_operational_risk > policy.max_operational_risk:
        blockers.append("operational_risk_above_threshold")

    time_signal = baseline.manual_minutes_per_30d >= policy.min_manual_minutes_per_30d
    money_signal = (
        baseline.realized_loss_minor_per_30d is not None
        and baseline.realized_loss_minor_per_30d >= policy.min_realized_loss_minor_per_30d
        and baseline.realized_loss_minor_per_30d > 0
    )
    if time_signal:
        reasons.append("manual_time_loss")
    if money_signal:
        reasons.append("verified_realized_money_loss")
    if baseline.revenue_at_risk_minor_per_30d is not None and baseline.revenue_at_risk_minor_per_30d > 0:
        reasons.append("revenue_at_risk_observed_not_counted_as_realized_loss")
    if not time_signal and not money_signal:
        blockers.append("no_material_time_or_verified_money_loss")
    if baseline.money_status is MoneyStatus.PARTIAL:
        reasons.append("money_evidence_partial_not_used_for_total_loss")
    elif baseline.money_status is MoneyStatus.MIXED_CURRENCY:
        reasons.append("mixed_currency_money_not_aggregated")

    opportunity_id = _stable_id(
        baseline.tenant_id,
        baseline.business_id,
        baseline.process_key,
        baseline.window_start.isoformat(),
        baseline.window_end.isoformat(),
        baseline.evidence_fingerprint,
        prefix="opp",
    )
    return AutomationOpportunity(
        opportunity_id=opportunity_id,
        baseline=baseline,
        priority_score=_priority_score(baseline, policy),
        reasons=tuple(reasons),
        eligible=not blockers,
        blockers=tuple(blockers),
    )


def discover_processes(
    observations: Iterable[ProcessObservation],
    *,
    policy: DiscoveryPolicy | None = None,
    generated_at: datetime | None = None,
) -> DiscoveryReport:
    resolved_policy = policy or DiscoveryPolicy()
    items = _dedupe_observations(tuple(observations))
    if not items:
        raise ValueError("discover_processes requires trusted process observations")
    tenant_ids = {item.tenant_id for item in items}
    business_ids = {item.business_id for item in items}
    if len(tenant_ids) != 1 or len(business_ids) != 1:
        raise ValueError("discovery input must be scoped to one tenant and one business")

    grouped: dict[str, list[ProcessObservation]] = defaultdict(list)
    for item in items:
        grouped[item.process_key].append(item)
    evaluated = [evaluate_opportunity(aggregate_baseline(group, resolved_policy), resolved_policy) for group in grouped.values()]
    eligible = sorted((item for item in evaluated if item.eligible), key=lambda item: (-item.priority_score, item.baseline.process_key))
    rejected = sorted((item for item in evaluated if not item.eligible), key=lambda item: (-item.priority_score, item.baseline.process_key))
    return DiscoveryReport(
        tenant_id=items[0].tenant_id,
        business_id=items[0].business_id,
        opportunities=tuple(eligible),
        rejected_processes=tuple(rejected),
        generated_at=generated_at or datetime.now(UTC),
    )
