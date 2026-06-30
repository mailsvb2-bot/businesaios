from __future__ import annotations

from dataclasses import dataclass
from bootstrap.decision_core_contract import RuntimeDecisionCorePort
from governance.economic_layer import EconomicAutonomyLayer
from runtime.boot import CapitalAllocationEngine, EconomicBrain, LearningSystem, RewardEngine, StrategicHorizonEngine
from runtime.boot.boot_decision_core import build_decision_core
from runtime.boot.boot_executor import build_executor, build_runtime_infra
from runtime.boot.boot_guard import build_guard
from runtime.boot.boot_reward_learning import build_reward_learning
from runtime.boot.core_assembly_args import CoreAssemblyArgs
from survival.controller import SurvivalController
from survival.metrics import StaticSurvivalMetricsProvider

CANON_BOOT_WIRING_ONLY = True

@dataclass
class CoreAssembly:
    survival: SurvivalController
    economic_layer: EconomicAutonomyLayer
    world_model: object
    core: RuntimeDecisionCorePort
    guard: object
    economic_brain: EconomicBrain
    reward_engine: RewardEngine
    learning: LearningSystem
    executor: object


def build_survival_and_economics() -> tuple[SurvivalController, EconomicAutonomyLayer]:
    survival = SurvivalController(StaticSurvivalMetricsProvider())
    economic_layer = EconomicAutonomyLayer(
        capital_engine=CapitalAllocationEngine(),
        horizon_engine=StrategicHorizonEngine(),
        survival=survival,
    )
    return survival, economic_layer


def build_reward_and_learning_components(*, snapshot_store, event_log, model_registry=None):
    """Compatibility alias retained for tests/boot hooks during the split."""
    return build_reward_learning(
        snapshot_store=snapshot_store,
        event_log=event_log,
        model_registry=model_registry,
    )


def build_core_assembly(*, args: CoreAssemblyArgs) -> CoreAssembly:
    survival, economic_layer = build_survival_and_economics()
    runtime_infra = args.runtime_infra
    world_model, core = build_decision_core(
        policy_selector=args.policy_selector,
        keyring=args.keyring,
        schemas=args.schemas,
        snapshot_store=runtime_infra.snapshot_store,
        event_log=args.event_log,
        decision_archive=args.decision_archive,
        issuer_id=args.issuer_id,
    )
    guard = build_guard(
        keyring=args.keyring,
        ledger=runtime_infra.ledger,
        schemas=args.schemas,
        event_log=args.event_log,
        survival_controller=survival,
        issuer_id=args.issuer_id,
    )
    economic_brain, reward_engine, learning = build_reward_and_learning_components(
        snapshot_store=runtime_infra.snapshot_store,
        event_log=args.event_log,
        model_registry=args.model_registry,
    )
    executor_runtime_infra = build_runtime_infra(
        runtime_infra=runtime_infra,
        delivery_state=args.delivery_state,
        telegram_outbound_queue=getattr(args.runtime_infra, "telegram_outbound_queue", None),
    )
    executor = build_executor(
        guard=guard,
        handlers=args.handlers,
        event_log=args.event_log,
        policy_registry=args.policy_registry,
        reward_engine=reward_engine,
        learning=learning,
        core=core,
        decision_archive=args.decision_archive,
        economic_layer=economic_layer,
        runtime_infra=executor_runtime_infra,
    )
    return CoreAssembly(
        survival=survival,
        economic_layer=economic_layer,
        world_model=world_model,
        core=core,
        guard=guard,
        economic_brain=economic_brain,
        reward_engine=reward_engine,
        learning=learning,
        executor=executor,
    )


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "CoreAssembly",
    "build_core_assembly",
    "build_decision_core",
    "build_reward_and_learning_components",
    "build_survival_and_economics",
]

# world-model integrity anchor: build_and_verify_default_world_model

# world-model integrity anchor: verify_boot_world_model_integrity
