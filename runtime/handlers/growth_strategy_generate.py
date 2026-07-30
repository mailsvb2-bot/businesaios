"""Thin adapter for canonical growth-strategy generation."""

from __future__ import annotations

from typing import Any

from runtime.growth import GrowthGoalV1, GrowthStrategyService
from runtime.handler_impl import growth_strategy_generate as _owner
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
CANON_GROWTH_STRATEGY_GENERATE_ADAPTER = True
ACTION_NAME = _owner.ACTION_NAME


def handle_growth_strategy_generate(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    event_store: Any,
    llm: Any = None,
    track_event_type: str = ACTION_NAME,
) -> Any:
    _owner.GrowthGoalV1 = GrowthGoalV1
    _owner.GrowthStrategyService = GrowthStrategyService
    return _owner.handle_growth_strategy_generate(
        payload,
        effects,
        env,
        event_store=event_store,
        llm=llm,
        track_event_type=track_event_type,
    )


def __getattr__(name: str) -> object:
    return getattr(_owner, name)


__all__ = ["ACTION_NAME", "handle_growth_strategy_generate"]
