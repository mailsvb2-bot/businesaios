from __future__ import annotations

from typing import Any


def dispatch(*, decide_fn: Any, execute_fn: Any, world_state: Any) -> Any:
    env = decide_fn(world_state)
    return execute_fn(env)
