from __future__ import annotations

from dataclasses import dataclass, field

from observability.tenant_metrics_registry import TenantMetricsRegistry

from .observability.anomaly_detector import SafetyAnomalyDetector
from .policy_trust_chain import PolicyTrustChain
from .rollback_verifier import RollbackVerifier
from .safety_slo import DEFAULT_SAFETY_SLO, SafetySLO

CANON_SAFETY_SUPERVISOR = True


@dataclass
class SafetySupervisor:
    metrics_registry: TenantMetricsRegistry
    trust_chain: PolicyTrustChain
    rollback_verifier: RollbackVerifier = field(default_factory=RollbackVerifier)
    slo: SafetySLO = field(default_factory=lambda: DEFAULT_SAFETY_SLO)
    anomaly_detector: SafetyAnomalyDetector = field(default_factory=SafetyAnomalyDetector)

    def record_intervention_ratio(self, *, tenant_id: str, ratio: float) -> bool:
        value = float(ratio)
        self.anomaly_detector.record(value)
        self.metrics_registry.set_gauge(tenant_id=tenant_id, metric_name='safety.intervention_ratio', value=value)
        anomalous = self.anomaly_detector.detect()
        self.metrics_registry.set_gauge(tenant_id=tenant_id, metric_name='safety.anomaly.active', value=1.0 if anomalous else 0.0)
        self.metrics_registry.set_gauge(tenant_id=tenant_id, metric_name='safety.slo.intervention_budget', value=float(self.slo.max_intervention_rate))
        return anomalous

    def record_failure_ratio(self, *, tenant_id: str, ratio: float) -> bool:
        value = float(ratio)
        self.metrics_registry.set_gauge(tenant_id=tenant_id, metric_name='safety.failure_ratio', value=value)
        breached = value > float(self.slo.max_failure_rate)
        self.metrics_registry.set_gauge(tenant_id=tenant_id, metric_name='safety.slo.failure_breached', value=1.0 if breached else 0.0)
        return breached


__all__ = ['CANON_SAFETY_SUPERVISOR', 'SafetySupervisor']
