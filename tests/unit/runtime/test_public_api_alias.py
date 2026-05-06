from __future__ import annotations

import runtime.world_state as world_state_namespace


def test_runtime_world_state_namespace_exposes_canonical_symbols() -> None:
    assert world_state_namespace.WORLD_STATE_CANON == "runtime.world_state"
    assert world_state_namespace.RUNTIME_WORLD_STATE_PUBLIC_API is True
    assert world_state_namespace.WorldStateV1.__name__ == "WorldStateV1"
