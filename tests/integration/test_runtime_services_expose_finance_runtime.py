from __future__ import annotations

from types import SimpleNamespace

from runtime.boot.system_builder_parts import runtime_services as mod


class _Ctx:
    def __init__(self) -> None:
        self.values: dict[str, object] = {"run_mode": "test", "env": "test"}

    def enter(self, _phase: object) -> None:
        return None

    def set_value(self, key: str, value: object, min_phase: object | None = None) -> None:
        del min_phase
        self.values[key] = value

    def get_value(self, key: str) -> object:
        return self.values.get(key)


def test_build_runtime_services_exposes_finance_runtime(monkeypatch) -> None:
    monkeypatch.setattr(mod, "boot_phase_30_durable_stores", lambda *args, **kwargs: (object(), object(), object(), object(), object(), object()))
    monkeypatch.setattr(mod, "build_event_log_and_bindings", lambda **kwargs: (object(), object()))
    monkeypatch.setattr(mod, "build_messaging_settings_gateway", lambda **kwargs: object())
    monkeypatch.setattr(mod, "EventLogMessagingPolicyEventStore", lambda event_log: object())
    monkeypatch.setattr(mod, "boot_messaging_policy_readmodel", lambda **kwargs: {"read_service": object()})
    monkeypatch.setattr(mod, "boot_phase_40_load_settings_and_flags", lambda: (SimpleNamespace(), object(), object()))
    monkeypatch.setattr(mod, "build_marketing_llm_components", lambda **kwargs: {"marketing_llm_composer": object(), "marketing_llm": object()})
    monkeypatch.setattr(mod, "validate_payments_webhook_prod_strict", lambda settings: None)
    monkeypatch.setattr(mod, "boot_phase_50_telegram_outbound_queue", lambda **kwargs: object())
    monkeypatch.setattr(mod, "resolve_tenant_and_pricing", lambda settings: (object(), "tenant-1"))
    monkeypatch.setattr(mod, "boot_phase_60_retention_adapter", lambda **kwargs: object())
    monkeypatch.setattr(mod, "wire_ads_stack_safely", lambda **kwargs: {})
    monkeypatch.setattr(mod, "boot_phase_70_policy_registry", lambda **kwargs: object())
    monkeypatch.setattr(mod, "emit_boot_completed", lambda **kwargs: None)

    import core.governance.readers.event_sourced_path as event_path
    import runtime.wiring as wiring

    monkeypatch.setattr(event_path, "assert_governance_event_store_contract", lambda store: None)
    monkeypatch.setattr(wiring, "build_behavior_graph_store", lambda *args, **kwargs: object())

    result = mod.build_runtime_services(
        ctx=_Ctx(),
        stack=object(),
        base=".",
        storage=object(),
        repo_root=".",
        model_registry_ctx=object(),
    )

    assert result.finance_runtime is not None
    assert sorted(result.finance_job_registry) == [
        "finance.run_allocation_rebalance",
        "finance.run_forecast",
        "finance.run_scenario_evaluation",
    ]
    assert sorted(result.finance_event_registry) == [
        "finance.allocation_recommended",
        "finance.forecast_revised",
        "finance.scenario_selected",
    ]
