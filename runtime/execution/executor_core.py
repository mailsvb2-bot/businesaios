"""Core execution helpers for RuntimeExecutor."""

from __future__ import annotations

from typing import Any
from governance.time_scale import TIME_SCALE_RULES, TimeScale, assert_action_allowed

def enforce_safe_mode(*, action: str) -> None:
    try:
        from runtime.safety import is_safe_mode
        if is_safe_mode() and str(action) != "noop@v1":
            raise RuntimeError("SAFE_MODE_FORBIDS_ACTION")
    except ImportError:
        return


def load_world(snapshot_store: Any, snapshot_id: str) -> Any:
    from governance.economic_layer import load_world_or_degraded

    return load_world_or_degraded(snapshot_store, str(snapshot_id))


def assert_timescale_allowed(*, action: str, timescale: TimeScale) -> None:
    assert_action_allowed(str(action), timescale)
    if not TIME_SCALE_RULES[timescale].allow_side_effects:
        raise RuntimeError(f"Side-effects forbidden on timescale: {timescale}")
