from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RETIRED = (
    "runtime.ai_ceo.public_api",
    "runtime.application.public_api",
    "runtime.behavior.public_api",
    "runtime.boot.public_api",
    "runtime.canon.public_api",
    "runtime.decision_input.public_api",
    "runtime.enforcement.public_api",
    "runtime.evolution.public_api",
    "runtime.experiments.public_api",
    "runtime.explainability.public_api",
    "runtime.finance.public_api",
    "runtime.growth.public_api",
    "runtime.human_governance.public_api",
    "runtime.idempotency.public_api",
    "runtime.knowledge.public_api",
    "runtime.learning_loop.public_api",
    "runtime.ledger.public_api",
    "runtime.llm.public_api",
    "runtime.marketing.public_api",
    "runtime.ml.public_api",
    "runtime.pricing.public_api",
    "runtime.product.public_api",
    "runtime.proofs.public_api",
    "runtime.queue.public_api",
    "runtime.ratelimit.public_api",
    "runtime.recovery_support.public_api",
    "runtime.revenue.public_api",
    "runtime.reward.public_api",
    "runtime.safety.public_api",
    "runtime.simulation.public_api",
    "runtime.state.public_api",
    "runtime.tenancy.public_api",
    "runtime.time.public_api",
    "runtime.ux.public_api",
    "runtime.world_model.public_api",
    "runtime.world_state.public_api",
)


def test_runtime_root_pseudofiles_are_retired() -> None:
    for dotted in RETIRED:
        relpath = dotted.replace(".", "/") + ".py"
        assert not (ROOT / relpath).exists(), relpath


def test_runtime_package_public_api_modules_remain_importable() -> None:
    for dotted in RETIRED:
        module = importlib.import_module(dotted)
        assert module is not None
