from __future__ import annotations

"""Read-only aggregation for inference runtime state.

This module owns no decision logic. It summarizes already-recorded runtime facts so
operator/API surfaces can present the same canonical picture.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import require_tenant_id
from observability.action_audit_log import ActionAuditLog
from observability.inference_budget_burn_log import InferenceBudgetBurnLog
from observability.inference_escalation_audit_log import InferenceEscalationAuditLog
from observability.inference_acceleration_log import InferenceAccelerationLog
from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore
from runtime.inference.providers.provider_health_monitor import InferenceProviderHealthMonitor


CANON_OBSERVABILITY_INFERENCE_RUNTIME_SUMMARY = True


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_text(value: Any) -> str:
    return str(value or '').strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _acceleration_batch_utilization_bucket(value: float) -> str:
    resolved = max(0.0, min(float(value), 1.0))
    if resolved < 0.34:
        return 'low'
    if resolved < 0.67:
        return 'medium'
    return 'high'


@dataclass(frozen=True)
class InferenceRuntimeSummaryService:
    state_store: InferenceCapacityStateStore
    provider_health_monitor: InferenceProviderHealthMonitor
    escalation_audit_log: InferenceEscalationAuditLog
    budget_burn_log: InferenceBudgetBurnLog
    action_audit_log: ActionAuditLog | None = None
    acceleration_log: InferenceAccelerationLog | None = None

    def _selection_records(self, *, tenant_id: str | None = None) -> tuple[Mapping[str, Any], ...]:
        if self.action_audit_log is None:
            return ()
        rows = self.action_audit_log.list_by_tenant(tenant_id=tenant_id, limit=500) if tenant_id else list(self.action_audit_log.records)
        items = []
        for row in rows:
            payload = _safe_dict(row.get('payload'))
            if _safe_text(payload.get('stage')) == 'inference.capacity_selection':
                items.append(row)
        return tuple(items)

    def _verification_records(self, *, tenant_id: str | None = None) -> tuple[Mapping[str, Any], ...]:
        if self.action_audit_log is None:
            return ()
        rows = self.action_audit_log.list_by_tenant(tenant_id=tenant_id, limit=500) if tenant_id else list(self.action_audit_log.records)
        items = []
        for row in rows:
            payload = _safe_dict(row.get('payload'))
            if _safe_text(payload.get('stage')) == 'inference.verification':
                items.append(row)
        return tuple(items)

    def _closed_loop_records(self, *, tenant_id: str | None = None) -> tuple[Mapping[str, Any], ...]:
        if self.action_audit_log is None:
            return ()
        rows = self.action_audit_log.list_by_tenant(tenant_id=tenant_id, limit=500) if tenant_id else list(self.action_audit_log.records)
        items = []
        for row in rows:
            payload = _safe_dict(row.get('payload'))
            if _safe_text(payload.get('stage')) == 'closed_loop.run_cycle':
                items.append(row)
        return tuple(items)

    def _provider_mix(self, *, tenant_id: str | None = None) -> tuple[dict[str, Any], ...]:
        selections = self._selection_records(tenant_id=tenant_id)
        if not selections:
            return ()
        provider_counts: Counter[str] = Counter()
        tier_counts: dict[str, str] = {}
        provider_costs: defaultdict[str, float] = defaultdict(float)
        total = 0
        for row in selections:
            payload = _safe_dict(row.get('payload'))
            provider_name = _safe_text(payload.get('provider_name')) or 'unknown'
            tier = _safe_text(payload.get('capacity_tier')) or 'unknown'
            provider_counts[provider_name] += 1
            tier_counts.setdefault(provider_name, tier)
            provider_costs[provider_name] += _safe_float(payload.get('estimated_cost_usd'))
            total += 1
        return tuple(
            {
                'provider_name': provider_name,
                'traffic_share': round(count / total, 6) if total else 0.0,
                'tier': tier_counts.get(provider_name, 'unknown'),
                'selection_count': int(count),
                'estimated_cost_usd': round(provider_costs.get(provider_name, 0.0), 6),
            }
            for provider_name, count in sorted(provider_counts.items(), key=lambda item: (-item[1], item[0]))
        )

    def _tier_mix(self, *, tenant_id: str | None = None) -> tuple[dict[str, Any], ...]:
        selections = self._selection_records(tenant_id=tenant_id)
        tier_counts: Counter[str] = Counter()
        for row in selections:
            payload = _safe_dict(row.get('payload'))
            tier_name = _safe_text(payload.get('capacity_tier')) or 'unknown'
            tier_counts[tier_name] += 1
        return tuple(
            {
                'capacity_tier': tier_name,
                'selection_count': int(count),
            }
            for tier_name, count in sorted(tier_counts.items(), key=lambda item: (-item[1], item[0]))
        )

    def _verification_summary(self, *, tenant_id: str | None = None) -> dict[str, Any]:
        records = self._verification_records(tenant_id=tenant_id)
        accepted = 0
        rejected = 0
        reasons: Counter[str] = Counter()
        for row in records:
            payload = _safe_dict(row.get('payload'))
            is_accepted = bool(payload.get('accepted'))
            reason = _safe_text(payload.get('verification_reason')) or 'unknown'
            accepted += 1 if is_accepted else 0
            rejected += 0 if is_accepted else 1
            reasons[reason] += 1
        return {
            'verification_count': len(records),
            'accepted_count': accepted,
            'rejected_count': rejected,
            'top_reasons': tuple(
                {'reason': reason, 'count': count}
                for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))[:5]
            ),
        }

    def _recent_escalations(self, *, tenant_id: str | None = None) -> tuple[dict[str, Any], ...]:
        rows = []
        for row in self._closed_loop_records(tenant_id=tenant_id):
            payload = _safe_dict(row.get('payload'))
            provider_name = _safe_text(payload.get('inference_provider_name'))
            capacity_tier = _safe_text(payload.get('inference_capacity_tier'))
            if not provider_name and not capacity_tier:
                continue
            rows.append(
                {
                    'provider_name': provider_name or None,
                    'capacity_tier': capacity_tier or None,
                    'status': _safe_text(row.get('status')) or 'unknown',
                    'recorded_at': _safe_text(row.get('recorded_at')),
                }
            )
        return tuple(rows[-10:])

    def _burn_summary(self, *, tenant_id: str | None = None) -> tuple[float, float]:
        budget_events = self.budget_burn_log.list_events()
        if budget_events:
            if tenant_id is not None:
                budget_events = tuple(item for item in budget_events if _safe_text(getattr(item, 'tenant_id', '')) == tenant_id)
            if budget_events:
                latest = budget_events[-1]
                total_cost = round(sum(float(item.estimated_cost_usd) for item in budget_events), 6)
                return float(latest.estimated_cost_usd), total_cost
        selections = self._selection_records(tenant_id=tenant_id)
        if not selections:
            return 0.0, 0.0
        costs = [_safe_float(_safe_dict(row.get('payload')).get('estimated_cost_usd')) for row in selections]
        return round(costs[-1], 6), round(sum(costs), 6)


    def _acceleration_summary(self, *, tenant_id: str | None = None) -> dict[str, Any]:
        empty = {
            'event_count': 0,
            'execution_mode_mix': (),
            'device_class_mix': (),
            'transport_kind_mix': (),
            'local_memory_preference_mix': (),
            'provider_batch_utilization_mix': (),
            'pressure_band_mix': (),
            'locality_scope_mix': (),
            'average_batch_items': 0.0,
            'average_transfer_overhead_ms': 0.0,
            'average_batch_utilization_ratio': 0.0,
            'average_saturation_score': 0.0,
            'average_expected_queue_penalty_ms': 0.0,
        }
        if self.acceleration_log is None:
            return empty
        events = self.acceleration_log.list_events()
        if tenant_id is not None:
            events = tuple(item for item in events if _safe_text(getattr(item, 'tenant_id', '')) == tenant_id)
        if not events:
            return empty
        mode_counts: Counter[str] = Counter()
        device_counts: Counter[str] = Counter()
        transport_counts: Counter[str] = Counter()
        local_memory_counts: Counter[str] = Counter()
        utilization_counts: Counter[str] = Counter()
        pressure_counts: Counter[str] = Counter()
        locality_counts: Counter[str] = Counter()
        total_batch_items = 0
        total_transfer_overhead_ms = 0
        total_batch_utilization_ratio = 0.0
        total_saturation_score = 0.0
        total_expected_queue_penalty_ms = 0
        for item in events:
            mode_counts[_safe_text(getattr(item, 'execution_mode', '')) or 'unknown'] += 1
            device_counts[_safe_text(getattr(item, 'device_class', '')) or 'unknown'] += 1
            transport_counts[_safe_text(getattr(item, 'transport_kind', '')) or 'unknown'] += 1
            local_memory_counts['local' if bool(getattr(item, 'prefers_local_memory', False)) else 'remote'] += 1
            batch_items = max(int(getattr(item, 'batch_items', 0)), 1)
            provider_max_batch_items = max(int(getattr(item, 'provider_max_batch_items', 1)), 1)
            utilization_ratio = min(batch_items / provider_max_batch_items, 1.0)
            utilization_bucket = _acceleration_batch_utilization_bucket(utilization_ratio)
            utilization_counts[utilization_bucket] += 1
            pressure_counts[_safe_text(getattr(item, 'pressure_band', '')) or 'unknown'] += 1
            locality_counts[_safe_text(getattr(item, 'locality_scope', '')) or 'unknown'] += 1
            total_batch_items += batch_items
            total_transfer_overhead_ms += int(getattr(item, 'expected_transfer_overhead_ms', 0))
            total_batch_utilization_ratio += utilization_ratio
            total_saturation_score += max(0.0, min(float(getattr(item, 'saturation_score', 0.0)), 1.0))
            total_expected_queue_penalty_ms += int(getattr(item, 'expected_queue_penalty_ms', 0))
        return {
            'event_count': len(events),
            'execution_mode_mix': tuple(
                {'execution_mode': mode, 'count': count}
                for mode, count in sorted(mode_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            'device_class_mix': tuple(
                {'device_class': device_class, 'count': count}
                for device_class, count in sorted(device_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            'transport_kind_mix': tuple(
                {'transport_kind': kind, 'count': count}
                for kind, count in sorted(transport_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            'local_memory_preference_mix': tuple(
                {'memory_preference': preference, 'count': count}
                for preference, count in sorted(local_memory_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            'provider_batch_utilization_mix': tuple(
                {'utilization_band': band, 'count': count}
                for band, count in sorted(utilization_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            'pressure_band_mix': tuple(
                {'pressure_band': band, 'count': count}
                for band, count in sorted(pressure_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            'locality_scope_mix': tuple(
                {'locality_scope': scope, 'count': count}
                for scope, count in sorted(locality_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
            'average_batch_items': round(total_batch_items / len(events), 6),
            'average_transfer_overhead_ms': round(total_transfer_overhead_ms / len(events), 6),
            'average_batch_utilization_ratio': round(total_batch_utilization_ratio / len(events), 6),
            'average_saturation_score': round(total_saturation_score / len(events), 6),
            'average_expected_queue_penalty_ms': round(total_expected_queue_penalty_ms / len(events), 6),
        }

    def build(self, *, tenant_id: str | None = None) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id) if tenant_id is not None else None
        state = self.state_store.get()
        providers = tuple(
            {
                'provider_name': item.provider_name,
                'healthy': bool(item.healthy),
                'availability_score': float(item.availability_score),
                'latency_score': float(item.latency_score),
                'error_rate': float(item.error_rate),
                'saturation_score': float(item.saturation_score),
                'tier': 'unknown',
            }
            for item in self.provider_health_monitor.snapshots()
        )
        escalation_events = self.escalation_audit_log.list_events()
        if required_tenant_id is not None:
            escalation_events = tuple(
                item
                for item in escalation_events
                if _safe_text(getattr(item, 'tenant_id', '')) == required_tenant_id
            )
        burn_rate_usd_per_hour, total_estimated_cost_usd = self._burn_summary(tenant_id=required_tenant_id)
        provider_mix = self._provider_mix(tenant_id=required_tenant_id)
        return {
            'tenant_id': required_tenant_id,
            'active_tier': state.active_tier.value,
            'frozen': bool(state.frozen),
            'providers': providers,
            'provider_mix': provider_mix,
            'tier_mix': self._tier_mix(tenant_id=required_tenant_id),
            'verification_summary': self._verification_summary(tenant_id=required_tenant_id),
            'escalation_event_count': len(escalation_events),
            'recent_escalations': self._recent_escalations(tenant_id=required_tenant_id),
            'headroom_usd': 0.0,
            'burn_rate_usd_per_hour': burn_rate_usd_per_hour,
            'total_estimated_cost_usd': total_estimated_cost_usd,
            'selection_count': sum(int(item['selection_count']) for item in provider_mix),
            'acceleration_summary': self._acceleration_summary(tenant_id=required_tenant_id),
            'read_only': True,
            'tenant_bound': required_tenant_id is not None,
        }


__all__ = ['CANON_OBSERVABILITY_INFERENCE_RUNTIME_SUMMARY', 'InferenceRuntimeSummaryService']
