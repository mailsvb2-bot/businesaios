from __future__ import annotations

from presentation import (
    AcquisitionInputField,
    AcquisitionInputSchema,
    CANON_PRESENTATION_ACQUISITION_INPUT_SCHEMA,
    acquisition_input_schema,
)


def test_presentation_input_schema_marker_is_enabled() -> None:
    assert CANON_PRESENTATION_ACQUISITION_INPUT_SCHEMA is True


def test_acquisition_input_schema_returns_canonical_structure() -> None:
    schema = acquisition_input_schema()

    assert isinstance(schema, AcquisitionInputSchema)
    assert all(isinstance(field, AcquisitionInputField) for field in schema.fields)
    assert schema.keys() == (
        "target_customers",
        "total_budget",
        "daily_budget",
        "target_days",
        "cost_per_entry",
        "gross_margin_ltv",
        "setup_cost",
        "max_cac_to_ltv_ratio",
        "payback_horizon_months",
        "expected_monthly_margin_per_customer",
    )


def test_acquisition_input_schema_field_ranges_are_valid() -> None:
    schema = acquisition_input_schema()
    for field in schema.fields:
        assert field.minimum <= field.default <= field.maximum, field.key
        assert field.step > 0, field.key
        assert field.control == "range", field.key


def test_acquisition_input_schema_uses_translation_keys_not_ui_copy() -> None:
    schema = acquisition_input_schema()
    for field in schema.fields:
        assert "." in field.label_key, field.key
        assert "." in field.description_key, field.key


def test_acquisition_input_schema_supports_field_lookup() -> None:
    schema = acquisition_input_schema()
    field = schema.field("target_customers")
    assert field.key == "target_customers"
    assert field.unit == "customers"

    try:
        schema.field("missing")
    except KeyError as exc:
        assert str(exc).strip("'") == "missing"
    else:
        raise AssertionError("KeyError was not raised for missing field")
