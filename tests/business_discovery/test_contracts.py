from __future__ import annotations

import pytest

from application.business_discovery import (
    DiscoveryValueKind,
    discovery_field_spec,
    normalize_discovery_value,
)


def test_discovery_field_contract_preserves_legacy_money_semantics() -> None:
    spec = discovery_field_spec("economics.average_check")
    assert spec.value_kind is DiscoveryValueKind.MONEY_MINOR
    assert normalize_discovery_value(
        spec,
        {"amount_minor": 125_000, "currency": "rub"},
    ) == {"amount_minor": 125_000, "currency": "RUB"}


@pytest.mark.parametrize(
    "value",
    (
        {"amount_minor": -1, "currency": "RUB"},
        {"amount_minor": True, "currency": "RUB"},
        {"amount_minor": 100, "currency": "R"},
        {"amount_minor": 100, "currency": "RUB", "extra": 1},
        100,
    ),
)
def test_discovery_money_contract_fails_closed(value) -> None:
    with pytest.raises(ValueError):
        normalize_discovery_value(
            discovery_field_spec("economics.average_check"),
            value,
        )


@pytest.mark.parametrize("value", (-0.1, 100.1, float("nan"), True, "50"))
def test_discovery_margin_contract_fails_closed(value) -> None:
    with pytest.raises(ValueError, match="0 to 100"):
        normalize_discovery_value(
            discovery_field_spec("economics.margin_pct"),
            value,
        )


def test_discovery_margin_accepts_closed_percentage_range() -> None:
    spec = discovery_field_spec("economics.margin_pct")
    assert normalize_discovery_value(spec, 0) == 0
    assert normalize_discovery_value(spec, 37.5) == 37.5
    assert normalize_discovery_value(spec, 100) == 100


@pytest.mark.parametrize(
    ("raw", "expected"),
    (("YES", "yes"), (" no ", "no"), ("Some", "some")),
)
def test_discovery_client_presence_has_one_canonical_vocabulary(raw, expected) -> None:
    spec = discovery_field_spec("sales.has_clients")
    assert normalize_discovery_value(spec, raw) == expected


def test_discovery_client_presence_reserves_unknown_for_epistemic_flag() -> None:
    with pytest.raises(ValueError):
        normalize_discovery_value(
            discovery_field_spec("sales.has_clients"),
            "unknown",
        )


def test_discovery_text_contract_is_scalar_non_empty_and_normalized() -> None:
    spec = discovery_field_spec("identity.industry")
    assert normalize_discovery_value(spec, "  medical_services  ") == "medical_services"
    with pytest.raises(ValueError):
        normalize_discovery_value(spec, {"industry": "medical_services"})
    with pytest.raises(ValueError):
        normalize_discovery_value(spec, "   ")
