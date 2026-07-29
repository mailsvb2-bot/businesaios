"""Thin adapter for the canonical Ads RL training handler."""

from __future__ import annotations

from typing import Any

from runtime.ads import DatasetBuilder, OPEGate, RewardComputer, RewardWindow, RLTrainer, bind_runtime_state, maturity_gate, policy_store
from runtime.governance import ProfitMetricsService
from runtime.handler_impl import ads_rl_train_tick as _owner
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
CANON_ADS_RL_TRAIN_ADAPTER = True
ACTION_NAME = _owner.ACTION_NAME

_SYNCED_DEPENDENCIES = (
    "DatasetBuilder",
    "OPEGate",
    "RewardComputer",
    "RewardWindow",
    "RLTrainer",
    "bind_runtime_state",
    "maturity_gate",
    "policy_store",
    "ProfitMetricsService",
)


def _sync_dependencies() -> None:
    for name in _SYNCED_DEPENDENCIES:
        setattr(_owner, name, globals()[name])


def handle_ads_rl_train_tick(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    event_store: Any,
) -> Any:
    _sync_dependencies()
    return _owner.handle_ads_rl_train_tick(
        payload,
        effects,
        env,
        event_store=event_store,
    )


def __getattr__(name: str) -> object:
    return getattr(_owner, name)


__all__ = ["ACTION_NAME", "handle_ads_rl_train_tick"]
