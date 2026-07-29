"""Thin adapter for the canonical reward-observation handler."""

from __future__ import annotations

from typing import Any

from runtime.handler_impl import reward_observe as _owner
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
CANON_REWARD_OBSERVE_ADAPTER = True
ACTION_NAME = _owner.ACTION_NAME
RewardComputer = _owner.RewardComputer
ProfitMetricsService = _owner.ProfitMetricsService


def handle_reward_observe(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    event_store: Any,
) -> Any:
    return _owner.handle_reward_observe(
        payload,
        effects,
        env,
        event_store=event_store,
        reward_computer_cls=RewardComputer,
        profit_metrics_service_cls=ProfitMetricsService,
    )


def __getattr__(name: str) -> object:
    return getattr(_owner, name)


__all__ = ["ACTION_NAME", "ProfitMetricsService", "RewardComputer", "handle_reward_observe"]
