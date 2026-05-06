from __future__ import annotations

from datetime import timedelta

from observability.alert_rule_contract import AlertComparator, AlertRule, AlertSeverity, AlertWindow
from observability.alerting_policy import AlertingPolicy
from observability.sli_collector import SLICollector
from observability.slo_contract import SLIKind, SLOComparator, SLODefinition
from observability.tenant_metrics_registry import MetricAggregation, TenantMetricsRegistry, utc_now


TENANT_ID = "tenant-a"


def test_alerting_policy_respects_windowed_metric_snapshot() -> None:
    registry = TenantMetricsRegistry()
    old = utc_now() - timedelta(seconds=3600)
    registry.emit(
        tenant_id=TENANT_ID,
        metric_name="runtime.error_rate",
        kind=SLIKind.ERROR_RATE,
        value=0.90,
        aggregation=MetricAggregation.AVG,
        emitted_at=old,
    )
    registry.emit(
        tenant_id=TENANT_ID,
        metric_name="runtime.error_rate",
        kind=SLIKind.ERROR_RATE,
        value=0.02,
        aggregation=MetricAggregation.AVG,
    )

    policy = AlertingPolicy(metrics_registry=registry)
    rule = AlertRule(
        rule_id="error-rate-high",
        tenant_id=TENANT_ID,
        metric_name="runtime.error_rate",
        comparator=AlertComparator.GTE,
        threshold=0.05,
        severity=AlertSeverity.HIGH,
        window=AlertWindow(seconds=300),
    )
    assert policy.evaluate_rule(rule) is None


def test_sli_collector_and_slo_evaluation_use_runtime_metrics_without_business_logic() -> None:
    registry = TenantMetricsRegistry()
    registry.observe_latency_ms(tenant_id=TENANT_ID, metric_name="runtime.latency_ms", value_ms=120.0)
    registry.observe_latency_ms(tenant_id=TENANT_ID, metric_name="runtime.latency_ms", value_ms=200.0)
    collector = SLICollector(metrics_registry=registry)
    reading = collector.collect(tenant_id=TENANT_ID, sli_name="runtime.latency_ms")
    assert reading is not None
    assert reading.sli_kind is SLIKind.LATENCY_P95_MS
    slo = SLODefinition(
        slo_id="latency-p95",
        tenant_id=TENANT_ID,
        sli_name="runtime.latency_ms",
        sli_kind=SLIKind.LATENCY_P95_MS,
        comparator=SLOComparator.LTE,
        target_value=250.0,
    )
    evaluation = collector.evaluate(slo)
    assert evaluation is not None
    assert evaluation.is_compliant is True
