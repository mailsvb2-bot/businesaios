import pytest

from observability.execution_metrics import ExecutionMetrics
from observability.experiment_metrics import ExperimentMetrics
from observability.lead_metrics import LeadMetrics


@pytest.mark.parametrize('cls', [ExecutionMetrics, ExperimentMetrics, LeadMetrics])
def test_metric_aliases_share_counter_behavior(cls):
    metrics = cls()
    metrics.observe('hits')
    metrics.observe('hits', 2.5)
    assert metrics.values['hits'] == 3.5
