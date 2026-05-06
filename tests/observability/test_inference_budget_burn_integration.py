from observability.inference_budget_burn_log import InferenceBudgetBurnLog
from runtime.execution.executor_observability import record_inference_budget_burn


class _Decision:
    def __init__(self):
        self.payload = {
            'tenant_id': 'tenant-a',
            'inference_provider_name': 'local_gpu_provider',
            'inference_capacity_tier': 'local_gpu',
            'inference_estimated_cost_usd': 1.75,
        }


class _Env:
    def __init__(self):
        self.decision = _Decision()


def test_inference_budget_burn_log_records_from_executor_observability():
    log = InferenceBudgetBurnLog()
    record_inference_budget_burn(budget_burn_log=log, env=_Env(), safe_dict=lambda x: dict(x))
    rows = log.list_events()
    assert len(rows) == 1
    assert rows[0].estimated_cost_usd == 1.75
