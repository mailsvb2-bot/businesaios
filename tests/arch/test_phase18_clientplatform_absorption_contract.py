from __future__ import annotations

from scripts.check_phase18_clientplatform_absorption import (
    is_phase18_complete,
    load_manifest,
    validate_manifest,
)


def test_phase18_absorption_manifest_is_complete_as_inventory_and_schema_valid() -> None:
    data = load_manifest()
    assert not validate_manifest(data)


def test_phase18_cannot_be_claimed_complete_before_decommission_evidence() -> None:
    data = load_manifest()
    assert is_phase18_complete(data) is False
