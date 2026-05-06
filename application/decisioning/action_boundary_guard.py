from __future__ import annotations

import canon.action_boundary_rules as _action_boundary_rules


def assert_safe_action_boundary(payload: dict[str, object]) -> None:
    _action_boundary_rules.assert_action_boundary_clean(payload)
