from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from collections.abc import Mapping


CANON_MARKET_INTELLIGENCE_OBSERVABILITY = True


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _truncate(value: Any, *, max_text_length: int) -> Any:
    if isinstance(value, str):
        text = value.strip()
        return text[:max_text_length] if len(text) > max_text_length else text
    if isinstance(value, dict):
        return {str(k): _truncate(v, max_text_length=max_text_length) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_truncate(v, max_text_length=max_text_length) for v in value]
    return value


@dataclass(frozen=True)
class IngestionTraceSpan:
    trace_id: str
    run_id: str
    tenant_id: str
    provider: str
    source_family: str
    operation: str
    started_at: str
    finished_at: str | None = None
    status: str = 'running'
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            'trace_id': self.trace_id,
            'run_id': self.run_id,
            'tenant_id': self.tenant_id,
            'provider': self.provider,
            'source_family': self.source_family,
            'operation': self.operation,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'status': self.status,
            'metadata': dict(self.metadata),
        }


@dataclass
class MarketIntelligenceTelemetry:
    max_events: int = 1000
    max_text_length: int = 512
    _events: list[dict[str, Any]] = field(default_factory=list)
    _counters: dict[str, float] = field(default_factory=dict)
    _traces: dict[str, IngestionTraceSpan] = field(default_factory=dict)

    def emit(self, name: str, **payload: Any) -> None:
        normalized_name = str(name).strip()
        normalized_payload = _truncate(dict(payload), max_text_length=int(self.max_text_length))
        self._events.append({'event': normalized_name, 'at': _utc_now(), 'payload': normalized_payload})
        if len(self._events) > int(self.max_events):
            self._events = self._events[-int(self.max_events):]
        self._counters[normalized_name] = float(self._counters.get(normalized_name, 0.0)) + 1.0

    def count(self, name: str) -> int:
        return int(self._counters.get(str(name).strip(), 0.0))

    def start_trace(self, *, trace_id: str, run_id: str, tenant_id: str, provider: str, source_family: str, operation: str, **metadata: Any) -> None:
        self._traces[trace_id] = IngestionTraceSpan(trace_id=trace_id, run_id=run_id, tenant_id=tenant_id, provider=provider, source_family=source_family, operation=operation, started_at=_utc_now(), metadata=dict(metadata))

    def finish_trace(self, *, trace_id: str, status: str, **metadata: Any) -> None:
        current = self._traces.get(trace_id)
        if current is None:
            return
        self._traces[trace_id] = IngestionTraceSpan(
            trace_id=current.trace_id,
            run_id=current.run_id,
            tenant_id=current.tenant_id,
            provider=current.provider,
            source_family=current.source_family,
            operation=current.operation,
            started_at=current.started_at,
            finished_at=_utc_now(),
            status=str(status),
            metadata={**dict(current.metadata), **dict(metadata)},
        )

    def observe_latency(self, *, provider: str, source_family: str, latency_ms: float) -> None:
        self._inc(f'provider_latency_count:{provider}')
        self._inc(f'provider_latency_sum_ms:{provider}', float(latency_ms))
        self._inc(f'family_latency_count:{source_family}')
        self._inc(f'family_latency_sum_ms:{source_family}', float(latency_ms))

    def observe_rate_limit(self, *, provider: str) -> None:
        self._inc(f'provider_rate_limited:{provider}')

    def observe_error(self, *, provider: str, code: str) -> None:
        self._inc(f'provider_error:{provider}:{code}')

    def observe_freshness_lag(self, *, provider: str, lag_seconds: float) -> None:
        self._inc(f'provider_freshness_lag_count:{provider}')
        self._inc(f'provider_freshness_lag_sum:{provider}', float(lag_seconds))

    def observe_dedup_effectiveness(self, *, provider: str, before_count: int, after_count: int) -> None:
        self._inc(f'provider_dedup_before:{provider}', float(before_count))
        self._inc(f'provider_dedup_after:{provider}', float(after_count))

    def observe_source_quality(self, *, provider: str, score: float) -> None:
        self._inc(f'provider_quality_count:{provider}')
        self._inc(f'provider_quality_sum:{provider}', float(score))

    def emit_provenance_audit(self, *, tenant_id: str, evidence_id: str, source_provider: str, source_family: str, derived_kind: str, policy_name: str) -> None:
        self.emit('market_intelligence_provenance_audit', tenant_id=tenant_id, evidence_id=evidence_id, source_provider=source_provider, source_family=source_family, derived_kind=derived_kind, policy_name=policy_name)

    def anomaly_snapshot(self) -> dict[str, Any]:
        provider_errors = {k: v for k, v in self._counters.items() if k.startswith('provider_error:')}
        provider_rate_limits = {k: v for k, v in self._counters.items() if k.startswith('provider_rate_limited:')}
        return {
            'error_counters': provider_errors,
            'rate_limit_counters': provider_rate_limits,
            'high_error_providers': sorted([k for k, v in provider_errors.items() if v >= 5.0]),
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            'events': [dict(item) for item in self._events],
            'counters': dict(self._counters),
            'traces': {key: value.as_dict() for key, value in self._traces.items()},
            'anomalies': self.anomaly_snapshot(),
            'max_events': int(self.max_events),
        }

    def _inc(self, key: str, amount: float = 1.0) -> None:
        self._counters[key] = float(self._counters.get(key, 0.0)) + float(amount)


__all__ = ['CANON_MARKET_INTELLIGENCE_OBSERVABILITY', 'IngestionTraceSpan', 'MarketIntelligenceTelemetry']
