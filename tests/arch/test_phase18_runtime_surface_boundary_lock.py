from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime"

def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def test_runtime_handlers_keep_boundary_public_surfaces() -> None:
    cases = {
        "runtime/handlers/experiments_build.py": ["from runtime.experiments import"],
        "runtime/handlers/experiments_explain.py": ["from runtime.experiments import"],
        "runtime/handlers/product_build.py": ["from runtime.product import"],
        "runtime/handlers/product_explain.py": ["from runtime.product import"],
        "runtime/handlers/simulation_build.py": ["from runtime.simulation import"],
        "runtime/handlers/simulation_explain.py": ["from runtime.simulation import"],
        "runtime/handlers/human_governance_build.py": ["runtime.human_governance"],
        "runtime/handlers/human_governance_explain.py": ["runtime.human_governance"],
        "runtime/handlers/growth_score_candidates.py": ["from runtime.growth import"],
        "runtime/handlers/growth_strategy_backlog.py": ["from runtime.growth import"],
        "runtime/handlers/growth_strategy_generate.py": ["from runtime.growth import"],
        "runtime/handlers/growth_strategy_state.py": ["from runtime.growth import"],
        "runtime/handlers/learning_loop_build.py": ["from runtime.learning_loop import"],
        "runtime/handlers/learning_loop_explain.py": ["from runtime.learning_loop import"],
        "runtime/handlers/learning_loop_run.py": ["from runtime.learning_loop import"],
        "runtime/handlers/ml_score.py": ["from runtime.ml import"],
        "runtime/handlers/reward_observe_candidates.py": ["from runtime.reward import"],
        "runtime/_internal/effects_actions/llm_completion_support.py": ["from runtime.llm import LLMMessage, LLMRequest"],
        "runtime/audit/world_model_replay_audit.py": ["from runtime.world_model import replay_state_against_world_model"],
        "runtime/enforcement/rate_limit.py": ["from runtime.ratelimit import ("],
        "runtime/evolution/worker.py": ["from runtime.evolution import EvolutionOutbox, handle_evolution_job"],
        "runtime/handlers/behavior_graph.py": ["from runtime.behavior import BehaviorGraphStore, build_behavior_graph_from_events"],
        "runtime/handlers/pricing_select.py": ["from runtime.pricing import PricingRouteViolation, PricingSelectionContext"],
        "runtime/handlers/profit_sprint_onboarding.py": [
            "from runtime.ads import AdsApplyState, AdsPlan, plan_digest",
            "from runtime.idempotency import make_idempotency_key",
            "from runtime.ux import kb_ads_apply_pending",
        ],
        "runtime/integration/world_state_integration_service.py": ["from runtime.world_state import ("],
    }
    forbidden_prefixes = (
        "from core.experiments",
        "import core.experiments",
        "from core.product",
        "import core.product",
        "from core.simulation",
        "import core.simulation",
        "from core.human_governance",
        "import core.human_governance",
        "from core.growth",
        "import core.growth",
        "from core.learning_loop",
        "import core.learning_loop",
        "from core.ml",
        "import core.ml",
        "from core.reward",
        "import core.reward",
    )
    for rel, required in cases.items():
        text = _read(rel)
        for imp in required:
            assert imp in text, rel
        for prefix in forbidden_prefixes:
            assert prefix not in text, f"{rel} still imports {prefix}"

def test_runtime_surface_compat_shims_and_core_boundary_rules_stay_explicit() -> None:
    runtime_root = _read("runtime/__init__.py")
    assert '"llm_provider_factory": "runtime.llm"' in runtime_root
    assert "from core.llm" not in runtime_root

    runtime_perf = _read("runtime/observability/perf.py")
    assert "runtime.observability" in runtime_perf
    assert "from core.observability.perf" not in runtime_perf

    offenders: list[str] = []
    pattern = re.compile(r"^(?:from|import)\s+core\.", re.M)
    scoped_roots = [
        RUNTIME / "handlers",
        RUNTIME / "boot",
        RUNTIME / "integration",
        RUNTIME / "audit",
        RUNTIME / "enforcement",
        RUNTIME / "execution",
    ]
    allowed = {
        "runtime/boot/boot_core_assembly.py",
        "runtime/boot/boot_decision_core.py",
        "runtime/platform/support/policy/policy_factory.py",
        "runtime/platform/support/policy/policy_registry.py",
        "runtime/enforcement/signature_gate.py",
        "runtime/execution/executor_autonomy_gate.py",
        "runtime/integration/world_state_packet_support.py",
    }
    for scoped_root in scoped_roots:
        for path in scoped_root.rglob("*.py"):
            name = path.name
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            text = path.read_text(encoding="utf-8")
            if not pattern.search(text):
                continue
            if rel not in allowed and name not in {"public_api.py", "contract.py", "contracts.py", "__init__.py", "_surface.py"}:
                offenders.append(rel)
    assert offenders == [], offenders
