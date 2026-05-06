from __future__ import annotations

from runtime.handlers.ads_autopilot_tick_parts.engine_contract import (
    assert_request_safe,
    assert_tick_engine,
)


def execute_autopilot_tick(*, engine, req):
    assert_tick_engine(engine)
    assert_request_safe(req)
    return engine.tick(req)
