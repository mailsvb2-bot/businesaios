from __future__ import annotations

import pytest

from core.actions.catalog import build_catalog
from core.actions.names import ACTION_ROUTE_LEAD_V1
from core.safety.controls.action_catalog import build_default_action_catalog
from runtime.boot.actions_registry import SPECS


@pytest.mark.lock
def test_demand_route_has_one_closed_execution_and_safety_contract() -> None:
    schema = build_catalog()[ACTION_ROUTE_LEAD_V1].schema
    runtime_spec = SPECS[ACTION_ROUTE_LEAD_V1]
    safety_spec = build_default_action_catalog().resolve(ACTION_ROUTE_LEAD_V1)

    assert schema.allow_additional is False
    assert runtime_spec.requires_idempotency_key is True
    assert runtime_spec.execution_category == "advisory"
    assert runtime_spec.external_confirmation_mode == "not_required"

    assert safety_spec is not None
    assert safety_spec.action_prefix == ACTION_ROUTE_LEAD_V1
    assert safety_spec.blast_financial_amount == 0.0
    assert safety_spec.blast_users_affected == 0
    assert safety_spec.blast_records_affected == 0
    assert safety_spec.blast_services_touched == 0
    assert safety_spec.default_estimated_cost == 0.0
    assert safety_spec.approval_required is False
    assert safety_spec.simulation_required is False
    assert safety_spec.high_impact is False
