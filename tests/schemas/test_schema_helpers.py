from __future__ import annotations

import pytest

from schemas.action_schema import REQUIRED_FIELDS as ACTION_REQUIRED_FIELDS
from schemas.action_schema import validate as validate_action
from schemas.business_live_state_schema import BUSINESS_LIVE_STATE_SCHEMA
from schemas.helpers import required_fields_schema, validate_required_fields


def test_required_fields_schema_is_immutable_and_keeps_order() -> None:
    schema = required_fields_schema("a", "b", "c")
    assert schema["required"] == ("a", "b", "c")
    with pytest.raises(TypeError):
        schema["required"] = ("x",)


def test_required_fields_schema_rejects_blank_fields() -> None:
    with pytest.raises(ValueError):
        required_fields_schema("ok", "")


def test_validate_required_fields_returns_missing_fields_in_order() -> None:
    missing = validate_required_fields({"action_id": "1"}, ACTION_REQUIRED_FIELDS)
    assert missing == ["action_type", "channel"]


def test_existing_schema_constants_use_helper_shape() -> None:
    assert BUSINESS_LIVE_STATE_SCHEMA["required"] == (
        "business_id",
        "open_now",
        "capacity_score",
        "quality_score",
        "risk_score",
    )


def test_existing_validate_function_keeps_public_contract() -> None:
    assert validate_action({"action_id": "a", "channel": "ads"}) == ["action_type"]
