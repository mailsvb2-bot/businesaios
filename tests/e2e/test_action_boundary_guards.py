from __future__ import annotations

import pytest

from application.decisioning.action_boundary_guard import assert_safe_action_boundary


def test_action_boundary_guard_rejects_candidate_control() -> None:
    with pytest.raises(RuntimeError):
        assert_safe_action_boundary(
            {
                "external_world_state_features": {},
                "candidate_ids": ("a", "b"),
            }
        )
