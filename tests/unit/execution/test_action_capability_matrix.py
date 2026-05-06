from __future__ import annotations

from execution.action_capability_matrix import (
    build_action_capability_matrix,
    get_action_capability,
)


def test_action_capability_matrix_contains_known_actions() -> None:
    matrix = {entry.action_type: entry for entry in build_action_capability_matrix()}
    assert "create_listing" in matrix
    assert "ACTION_EXECUTE_PLAN_V1" in matrix
    assert matrix["create_listing"].approval_required is True
    assert matrix["create_listing"].bounded_by_blast_radius is True
    assert matrix["create_listing"].prod_ready is False


def test_internal_execution_token_is_not_reported_as_directly_executable() -> None:
    capability = get_action_capability("ACTION_EXECUTE_PLAN_V1")
    assert capability.decisionable is True
    assert capability.routable is False
    assert capability.executable is False
    assert capability.prod_ready is True
