from __future__ import annotations

from dataclasses import dataclass

CANON_PRESENTATION_ACQUISITION_INPUT_SCHEMA = True


@dataclass(frozen=True, slots=True)
class AcquisitionInputField:
    """
    Presentation-only metadata for external controls.

    Important:
    - no feasibility math here
    - no solver branching here
    - no localized prose inside acquisition domain
    """

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


def acquisition_input_schema() -> AcquisitionInputSchema:
    schema = AcquisitionInputSchema(
        fields=(
            AcquisitionInputField(
                key="target_customers",
                label_key="acquisition.target_customers.label",
                description_key="acquisition.target_customers.description",
                minimum=1,
                maximum=10_000,
                step=1,
                default=10,
                unit="customers",
            ),
            AcquisitionInputField(
                key="total_budget",
                label_key="acquisition.total_budget.label",
                description_key="acquisition.total_budget.description",
                minimum=0,
                maximum=1_000_000,
                step=10,
                default=1_000,
                unit="currency",
            ),
            AcquisitionInputField(
                key="daily_budget",
                label_key="acquisition.daily_budget.label",
                description_key="acquisition.daily_budget.description",
                minimum=0,
                maximum=100_000,
                step=1,
                default=100,
                unit="currency_per_day",
            ),
            AcquisitionInputField(
                key="target_days",
                label_key="acquisition.target_days.label",
                description_key="acquisition.target_days.description",
                minimum=1,
                maximum=3_650,
                step=1,
                default=30,
                unit="days",
            ),
            AcquisitionInputField(
                key="cost_per_entry",
                label_key="acquisition.cost_per_entry.label",
                description_key="acquisition.cost_per_entry.description",
                minimum=0.01,
                maximum=10_000,
                step=0.01,
                default=2.0,
                unit="currency_per_entry",
            ),
            AcquisitionInputField(
                key="gross_margin_ltv",
                label_key="acquisition.gross_margin_ltv.label",
                description_key="acquisition.gross_margin_ltv.description",
                minimum=0,
                maximum=1_000_000,
                step=1,
                default=300,
                unit="currency",
            ),
            AcquisitionInputField(
                key="setup_cost",
                label_key="acquisition.setup_cost.label",
                description_key="acquisition.setup_cost.description",
                minimum=0,
                maximum=1_000_000,
                step=1,
                default=0,
                unit="currency",
            ),
            AcquisitionInputField(
                key="max_cac_to_ltv_ratio",
                label_key="acquisition.max_cac_to_ltv_ratio.label",
                description_key="acquisition.max_cac_to_ltv_ratio.description",
                minimum=0.01,
                maximum=1.0,
                step=0.01,
                default=0.33,
                unit="ratio",
            ),
            AcquisitionInputField(
                key="payback_horizon_months",
                label_key="acquisition.payback_horizon_months.label",
                description_key="acquisition.payback_horizon_months.description",
                minimum=1,
                maximum=120,
                step=1,
                default=12,
                unit="months",
            ),
            AcquisitionInputField(
                key="expected_monthly_margin_per_customer",
                label_key="acquisition.expected_monthly_margin_per_customer.label",
                description_key="acquisition.expected_monthly_margin_per_customer.description",
                minimum=0,
                maximum=100_000,
                step=1,
                default=20,
                unit="currency_per_month",
            ),
        )
    )
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
