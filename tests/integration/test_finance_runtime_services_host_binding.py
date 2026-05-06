from __future__ import annotations

from types import SimpleNamespace

from runtime.boot.system_builder_parts.runtime_services_result import RuntimeServicesResult


def test_runtime_services_result_can_hold_finance_host_runtime_bindings() -> None:
    result = RuntimeServicesResult(
        host_job_catalog=SimpleNamespace(namespaces=lambda: ('finance',)),
        finance_event_read_model=SimpleNamespace(all=lambda: {'x': 1}),
        finance_observability=SimpleNamespace(counters=lambda: {'finance.job_completed': 1}),
    )
    assert result.host_job_catalog.namespaces() == ('finance',)
    assert result.finance_event_read_model.all() == {'x': 1}
    assert result.finance_observability.counters()['finance.job_completed'] == 1
