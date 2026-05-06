from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from observability.tenant_metrics_registry import TenantMetricsRegistry

from ..safety_supervisor import SafetySupervisor
from .metrics_export import SafetyMetricsExporter

CANON_SAFETY_EVENT_STORE = True


@dataclass(frozen=True)
class SafetyEvent:
    tenant_id: str
    action: str
    stage: str
    status: str
    control: str = ''
    reason: str = ''
    details: Mapping[str, Any] = field(default_factory=dict)
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class JsonlSafetyEventStore:
    def __init__(self, *, path: str, metrics_registry: TenantMetricsRegistry | None = None, supervisor: SafetySupervisor | None = None) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._metrics = SafetyMetricsExporter(metrics_registry) if metrics_registry is not None else None
        self._supervisor = supervisor

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: SafetyEvent) -> SafetyEvent:
        payload = {
            'tenant_id': str(event.tenant_id),
            'action': str(event.action),
            'stage': str(event.stage),
            'status': str(event.status),
            'control': str(event.control),
            'reason': str(event.reason),
            'details': dict(event.details),
            'observed_at': str(event.observed_at),
        }
        with self._lock:
            with self._path.open('a', encoding='utf-8') as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        if self._metrics is not None:
            try:
                self._metrics.record_event(event)
            except Exception:
                pass
        if self._supervisor is not None:
            try:
                self._supervisor.record_intervention_ratio(tenant_id=str(event.tenant_id), ratio=1.0 if str(event.status) in {'block', 'review'} else 0.0)
                if str(event.stage) == 'outcome':
                    self._supervisor.record_failure_ratio(tenant_id=str(event.tenant_id), ratio=0.0 if str(event.status) == 'success' else 1.0)
            except Exception:
                pass
        return event


__all__ = ['CANON_SAFETY_EVENT_STORE', 'JsonlSafetyEventStore', 'SafetyEvent']
