"""Thin adapter for the canonical Ads Apply execution handler."""

from __future__ import annotations

from typing import Any

from runtime.ads import AdsApplyEngine, bind_runtime_state, maturity_gate
from runtime.governance import ActuationRegistry
from runtime.handler_impl import ads_apply_execute as _owner
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
CANON_ADS_APPLY_EXECUTE_ADAPTER = True
ACTION_NAME = _owner.ACTION_NAME
_best_effort_route_ids = _owner._best_effort_route_ids


def handle_ads_apply_execute(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    engine: AdsApplyEngine | None,
    event_store: Any | None = None,
) -> Any:
    _owner.bind_runtime_state = bind_runtime_state
    _owner.maturity_gate = maturity_gate
    _owner.ActuationRegistry = ActuationRegistry
    return _owner.handle_ads_apply_execute(
        payload,
        effects,
        env,
        engine=engine,
        event_store=event_store,
    )


__all__ = ["ACTION_NAME", "_best_effort_route_ids", "handle_ads_apply_execute"]
