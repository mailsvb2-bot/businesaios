from __future__ import annotations

import pytest

from core.actions.catalog import build_catalog
from core.ai.schema_registry import DecisionSchema
from runtime.boot.actions_registry import all_actions


@pytest.mark.lock
def test_every_runtime_action_has_an_explicit_closed_schema() -> None:
    catalog = build_catalog()

    assert set(catalog) == all_actions()
    assert [
        action
        for action, entry in sorted(catalog.items())
        if entry.schema.allow_additional
    ] == []


@pytest.mark.lock
def test_marker_actions_preserve_their_exact_execution_payload_surface() -> None:
    catalog = build_catalog()
    expected_optional = {
        "tenant_id",
        "product_id",
        "user_id",
        "event_type",
        "payload",
        "source",
    }
    expected_types = {
        "tenant_id": str,
        "product_id": str,
        "user_id": str,
        "event_type": str,
        "payload": dict,
        "source": str,
    }

    for action in (
        "autopilot_decision@v1",
        "autopilot_run_started@v1",
        "autopilot_started@v1",
    ):
        schema = catalog[action].schema
        assert schema.required == set(), action
        assert schema.optional == expected_optional, action
        assert schema.field_types == expected_types, action
        assert schema.allow_additional is False, action


@pytest.mark.lock
def test_advisory_action_contracts_are_closed_without_losing_inputs() -> None:
    catalog = build_catalog()

    report = catalog["ads_rl_report@v1"].schema
    assert report == DecisionSchema(
        required={"tenant_id"},
        optional=set(),
        field_types={"tenant_id": str},
    )

    telegram = catalog["telegram_self_check@v1"].schema
    assert telegram == DecisionSchema(
        required=set(),
        optional={"token"},
        field_types={"token": str},
    )


@pytest.mark.lock
def test_catalog_assembly_fails_closed_on_registry_drift(monkeypatch) -> None:
    import core.actions.catalog as catalog_module

    monkeypatch.setattr(
        catalog_module,
        "ALLOWED_ACTIONS",
        (*catalog_module.ALLOWED_ACTIONS, "uncontracted_action@v1"),
    )

    with pytest.raises(
        RuntimeError,
        match=r"ACTION_SCHEMA_CATALOG_DRIFT:.*uncontracted_action@v1",
    ):
        catalog_module.build_catalog()



@pytest.mark.lock
def test_callback_query_id_and_idempotency_key_are_typed_reserved_fields() -> None:
    schema = DecisionSchema(
        required={"tenant_id"},
        optional=set(),
        field_types={"tenant_id": str},
    )
    schema.validate({
        "tenant_id": "tenant-live",
        "callback_query_id": "callback-12",
        "idempotency_key": "telegram:0123456789abcdef",
    })
    with pytest.raises(ValueError, match="BAD_PAYLOAD_TYPE"):
        schema.validate({"tenant_id": "tenant-live", "callback_query_id": 12})
    with pytest.raises(ValueError, match="BAD_PAYLOAD_TYPE"):
        schema.validate({"tenant_id": "tenant-live", "idempotency_key": None})
    with pytest.raises(ValueError, match="UNKNOWN_PAYLOAD_KEYS:forged"):
        schema.validate({"tenant_id": "tenant-live", "forged": True})
