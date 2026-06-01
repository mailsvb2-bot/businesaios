from __future__ import annotations

import math
from datetime import timedelta

import pytest

from tenancy.tenant_metrics_aggregator import TenantMetricsAggregator
from tenancy.tenant_metrics_contract import TenantMetricPoint, utc_now
from tenancy.tenant_metrics_prometheus_adapter import TenantMetricsPrometheusAdapter
from tenancy.tenant_metrics_store import InMemoryTenantMetricsStore


def test_inmemory_tenant_metrics_store_aggregates_counter_stream() -> None:
    store = InMemoryTenantMetricsStore()
    now = utc_now()

    store.increment(
        tenant_id='tenant-delta',
        metric_name='runtime.actions',
        amount=2.0,
        labels={'queue': 'default'},
        emitted_at=now,
    )
    store.increment(
        tenant_id='tenant-delta',
        metric_name='runtime.actions',
        amount=3.0,
        labels={'worker': 'worker-1'},
        emitted_at=now + timedelta(seconds=5),
    )
    store.append(
        TenantMetricPoint(
            tenant_id='tenant-delta',
            metric_name='runtime.active_runs',
            value=1.0,
            metric_type='gauge',
            emitted_at=now + timedelta(seconds=6),
            labels={'source': 'executor'},
        )
    )

    aggregate = store.aggregate(tenant_id='tenant-delta', metric_name='runtime.actions')
    assert aggregate is not None
    assert aggregate.sample_count == 2
    assert aggregate.total == 5.0
    assert aggregate.minimum == 2.0
    assert aggregate.maximum == 3.0
    assert aggregate.last_value == 3.0
    assert aggregate.labels['worker'] == 'worker-1'
    assert aggregate.label_series_count == 2
    assert aggregate.labels_collapsed is True

    snapshot = store.snapshot(tenant_id='tenant-delta')
    assert sorted(snapshot.metrics.keys()) == ['runtime.actions', 'runtime.active_runs']


def test_tenant_metrics_aggregator_merges_store_snapshot() -> None:
    store = InMemoryTenantMetricsStore()
    store.increment(tenant_id='tenant-epsilon', metric_name='runtime.connector_calls', amount=4.0)
    store.increment(tenant_id='tenant-epsilon', metric_name='runtime.connector_calls', amount=6.0)
    aggregator = TenantMetricsAggregator(store=store)

    report = aggregator.report(tenant_id='tenant-epsilon', metric_names=['runtime.connector_calls'])
    assert report.tenant_id == 'tenant-epsilon'
    assert len(report.emitted_metrics) == 1
    aggregate = report.emitted_metrics[0]
    assert aggregate.metric_name == 'runtime.connector_calls'
    assert aggregate.total == 10.0
    assert aggregate.sample_count == 2


def test_prometheus_adapter_sanitizes_metric_and_label_names() -> None:
    store = InMemoryTenantMetricsStore()
    store.increment(
        tenant_id='tenant-theta',
        metric_name='runtime/actions',
        amount=1.0,
        labels={'queue-name': 'primary"x'},
    )
    aggregate = store.aggregate(tenant_id='tenant-theta', metric_name='runtime/actions')
    assert aggregate is not None

    rendered = TenantMetricsPrometheusAdapter().render(aggregates=[aggregate])
    assert '# TYPE runtime_actions_total gauge' in rendered
    assert 'queue_name="primary\\"x"' in rendered


def test_metrics_store_rejects_mixed_metric_types_for_same_aggregate() -> None:
    store = InMemoryTenantMetricsStore()
    now = utc_now()
    store.append(TenantMetricPoint(tenant_id='tenant-mixed', metric_name='runtime.mixed', value=1.0, metric_type='counter', emitted_at=now))
    store.append(TenantMetricPoint(tenant_id='tenant-mixed', metric_name='runtime.mixed', value=2.0, metric_type='gauge', emitted_at=now + timedelta(seconds=1)))
    with pytest.raises(ValueError, match='mixed metric types'):
        store.aggregate(tenant_id='tenant-mixed', metric_name='runtime.mixed')


def test_metric_point_rejects_non_finite_values() -> None:
    point = TenantMetricPoint(tenant_id='tenant-bad', metric_name='runtime.nan', value=math.nan, metric_type='counter', emitted_at=utc_now())
    with pytest.raises(ValueError, match='finite'):
        point.validate()
