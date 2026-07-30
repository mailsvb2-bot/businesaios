"""Thin adapter for the canonical Ads RL suggestion handler."""

from __future__ import annotations

from typing import Any

from runtime.ads import RLSuggester, bind_runtime_state, policy_store
from runtime.governance import PolicyUpdateGate, PolicyUpdateGateError, ProfitMetricsService
from runtime.handler_impl import ads_rl_suggest as _owner
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
CANON_ADS_RL_SUGGEST_ADAPTER = True
ACTION_NAME = _owner.ACTION_NAME
_SUGGEST_GATE = _owner._SUGGEST_GATE


def handle_ads_rl_suggest(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    event_store: Any,
) -> Any:
    _owner.RLSuggester = RLSuggester
    _owner.bind_runtime_state = bind_runtime_state
    _owner.policy_store = policy_store
    _owner.PolicyUpdateGate = PolicyUpdateGate
    _owner.PolicyUpdateGateError = PolicyUpdateGateError
    _owner.ProfitMetricsService = ProfitMetricsService
    _owner._SUGGEST_GATE = _SUGGEST_GATE
    return _owner.handle_ads_rl_suggest(
        payload,
        effects,
        env,
        event_store=event_store,
    )


def __getattr__(name: str) -> object:
    return getattr(_owner, name)


__all__ = ["ACTION_NAME", "handle_ads_rl_suggest"]
