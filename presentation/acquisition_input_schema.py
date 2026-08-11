from __future__ import annotations

from dataclasses import dataclass

CANON_PRESENTATION_ACQUISITION_INPUT_SCHEMA = True


@dataclass(frozen=True, slots=True)
class AcquisitionInputField:
    """Presentation-only metadata; feasibility math stays in the acquisition domain."""

    key: str
    label_key: str
    description_key: str
    minimum: float
    maximum: float
    step: float
    default: float
    unit: str
    control: str = "range"


@dataclass(frozen=True, slots=True)
class AcquisitionInputSchema:
    fields: tuple[AcquisitionInputField, ...]

    def keys(self) -> tuple[str, ...]:
        return tuple(field.key for field in self.fields)

    def field(self, key: str) -> AcquisitionInputField:
        for field in self.fields:
            if field.key == key:
                return field
        raise KeyError(key)


_FIELD_SPECS = (
    ("target_customers", 1, 10_000, 1, 10, "customers"),
    ("total_budget", 0, 1_000_000, 10, 1_000, "currency"),
    ("daily_budget", 0, 100_000, 1, 100, "currency_per_day"),
    ("target_days", 1, 3_650, 1, 30, "days"),
    ("cost_per_entry", 0.01, 10_000, 0.01, 2.0, "currency_per_entry"),
    ("gross_margin_ltv", 0, 1_000_000, 1, 300, "currency"),
    ("setup_cost", 0, 1_000_000, 1, 0, "currency"),
    ("max_cac_to_ltv_ratio", 0.01, 1.0, 0.01, 0.33, "ratio"),
    ("payback_horizon_months", 1, 120, 1, 12, "months"),
    ("expected_monthly_margin_per_customer", 0, 100_000, 1, 20, "currency_per_month"),
)


def acquisition_input_schema() -> AcquisitionInputSchema:
    schema = AcquisitionInputSchema(fields=tuple(
        AcquisitionInputField(
            key=key,
            label_key=f"acquisition.{key}.label",
            description_key=f"acquisition.{key}.description",
            minimum=minimum,
            maximum=maximum,
            step=step,
            default=default,
            unit=unit,
        )
        for key, minimum, maximum, step, default, unit in _FIELD_SPECS
    ))
    _validate_schema(schema)
    return schema


def _validate_schema(schema: AcquisitionInputSchema) -> None:
    seen: set[str] = set()
    for field in schema.fields:
        if field.key in seen:
            raise ValueError(f"duplicate acquisition input field key: {field.key}")
        seen.add(field.key)
        if field.step <= 0:
            raise ValueError(f"field step must be positive: {field.key}")
        if field.minimum > field.maximum:
            raise ValueError(f"field minimum must be <= maximum: {field.key}")
        if not (field.minimum <= field.default <= field.maximum):
            raise ValueError(f"field default must stay within range: {field.key}")


__all__ = [
    "AcquisitionInputField",
    "AcquisitionInputSchema",
    "CANON_PRESENTATION_ACQUISITION_INPUT_SCHEMA",
    "acquisition_input_schema",
]
