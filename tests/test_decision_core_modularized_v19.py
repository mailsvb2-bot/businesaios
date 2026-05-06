from importlib import import_module


def test_decision_pricing_helpers_resolve_via_core_ai_namespace() -> None:
    module = import_module("core.ai.decision_pricing")
    assert hasattr(module, "allowed_price_band")
    assert hasattr(module, "merge_price_constraints")
