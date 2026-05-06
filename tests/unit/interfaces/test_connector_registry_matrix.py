from __future__ import annotations

from interfaces.common.connector_registry_matrix import build_connector_registry_matrix_payload


def test_connector_registry_matrix_exposes_truth_layer() -> None:
    payload = build_connector_registry_matrix_payload()
    assert payload
    google_reviews = next(item for item in payload if item["connector_name"] == "google_reviews")
    assert google_reviews["domain"] == "reviews"
    assert google_reviews["implemented"] is True
    assert google_reviews["production_ready"] is False
    assert google_reviews["truth_layer"]["implemented"] is True
    assert google_reviews["truth_layer"]["verify_enabled"] is False


def test_connector_registry_matrix_includes_communications_domain() -> None:
    payload = build_connector_registry_matrix_payload()
    email = next(item for item in payload if item["connector_name"] == "email")
    assert email["domain"] == "communications"
    assert email["implemented"] is True
    assert email["verify"] is True
