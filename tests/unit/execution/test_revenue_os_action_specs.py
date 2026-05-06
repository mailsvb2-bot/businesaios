from __future__ import annotations

from execution.action_catalog import get_action_spec


def test_revenue_os_action_specs_are_advisory_only() -> None:
    spec = get_action_spec('catalog.revenue.apply_pricing_advisory')
    assert spec.action_class == 'revenue_advisory'
    assert spec.executable is False
    assert spec.idempotent is True
    assert spec.prod_ready is True
