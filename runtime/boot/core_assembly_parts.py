from __future__ import annotations

from typing import Any

from learning.registry import ArtifactRegistry
from runtime.boot import (
    EconomicBrain,
    EconomicReward,
    GrowthPolicy,
    LearningSystem,
    LTVEstimator,
    PricingPolicy,
    RewardEngine,
)

CANON_BOOT_WIRING_ONLY = True

def build_economic_brain() -> EconomicBrain:
    return EconomicBrain(
        ltv=LTVEstimator(),
        pricing=PricingPolicy(),
        growth=GrowthPolicy(),
        reward=EconomicReward(),
    )


def build_reward_and_learning_components(*, snapshot_store: Any, event_log: Any, model_registry: Any | None = None) -> tuple[EconomicBrain, RewardEngine, LearningSystem]:
    economic_brain = build_economic_brain()
    reward_engine = RewardEngine(
        snapshot_store=snapshot_store,
        economic_brain=economic_brain,
        event_log=event_log,
    )
    reg = model_registry if model_registry is not None else ArtifactRegistry()
    learning = LearningSystem(model_registry=reg)
    return economic_brain, reward_engine, learning
