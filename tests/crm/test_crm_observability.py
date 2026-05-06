from observability.crm.crm_metrics import CrmMetrics
from observability.crm.crm_sli_collector import CrmSliCollector


def test_observability_collects_metrics():
    metrics = CrmMetrics(); metrics.inc('writes_verified')
    assert CrmSliCollector().snapshot(metrics)['writes_verified'] == 1
