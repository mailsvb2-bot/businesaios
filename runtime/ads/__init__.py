"""Canonical runtime Ads boundary surface.

Runtime wiring, handlers, and jobs should depend on this module instead of
reaching into scattered core.ads/core.growth internals directly.
"""

from __future__ import annotations

from core.ads.ads_service import AdsCommand, AdsGuardrails, AdsPlan, AdsPort, AdsService
from core.ads.apply.contract import AdsApplyRequest
from core.ads.apply.limits import AdsApplyLimits
from core.ads.apply.plan_digest import plan_digest
from core.ads.apply_engine import AdsApplyEngine, AdsApplyEnv
from core.ads.apply_gate import AdsApplyState
from core.ads.autopilot.campaign_builder import AdsAutopilotCampaignBuilder
from core.ads.autopilot.contract import AdsAutopilotConstraints, AdsAutopilotRequest
from core.ads.autopilot.engine import AdsAutopilotEngine
from core.ads.hardening.kill_switch import AdsKillSwitch
from core.ads.hardening.rate_limiter import AdsRateLimiter
from core.ads.rl.dataset import DatasetBuilder
from core.ads.rl.ope import OPEGate
from core.ads.rl.reward import RewardComputer, RewardWindow
from core.ads.rl.runtime_state import bind_runtime_state, maturity_gate, policy_store
from core.ads.rl.suggester import RLSuggester
from core.ads.rl.trainer import RLTrainer
from core.api.idempotency import IdempotencyKey, MemoryIdempotencyStore
from core.events.event_types import DECISION_EXECUTED
from core.growth.ads.rl import AdsRLOptimizerDeps, AdsRLOptimizerService
from core.growth.ads.rl.observer import ObserveTickResult, observe_tick_once
from core.growth.autopilot_scheduler import AutopilotTarget
from core.growth.budget_guardrails import BudgetGuardrails, DailyLimits
from core.growth.campaign_builder.service import AutopilotCampaignBuilder
from core.growth.circuit_breaker import BreakerConfig, CircuitBreaker
from core.growth.event_sink import EventLogSink
from core.growth.spend_ledger_event_store import EventStoreSpendLedger

__all__ = [
    'CANON_RUNTIME_ADS_NAMESPACE',
    "AdsApplyEngine",
    "AdsApplyEnv",
    "AdsApplyLimits",
    "AdsApplyRequest",
    "AdsApplyState",
    "AdsAutopilotCampaignBuilder",
    "AdsAutopilotConstraints",
    "AdsAutopilotEngine",
    "AdsAutopilotRequest",
    "AdsCommand",
    "AdsGuardrails",
    "AdsKillSwitch",
    "AdsPlan",
    "AdsPort",
    "AdsRLOptimizerDeps",
    "AdsRLOptimizerService",
    "AdsRateLimiter",
    "AdsService",
    "AutopilotCampaignBuilder",
    "AutopilotTarget",
    "BreakerConfig",
    "BudgetGuardrails",
    "CircuitBreaker",
    "DatasetBuilder",
    "DailyLimits",
    "DECISION_EXECUTED",
    "EventLogSink",
    "EventStoreSpendLedger",
    "IdempotencyKey",
    "MemoryIdempotencyStore",
    "OPEGate",
    "ObserveTickResult",
    "RLSuggester",
    "RLTrainer",
    "RewardComputer",
    "RewardWindow",
    "bind_runtime_state",
    "maturity_gate",
    "observe_tick_once",
    "plan_digest",
    "policy_store",
]
CANON_RUNTIME_ADS_NAMESPACE = True

