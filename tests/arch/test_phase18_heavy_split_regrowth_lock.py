from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def test_heavy_split_delegations_and_helper_modules_stay_collapsed() -> None:
    scheduler = _read("runtime/scheduler.py")
    assert "from runtime.scheduler_run_cycle import run_learning_cycle" in scheduler
    assert "return run_learning_cycle(self)" in scheduler

    strategic = _read("core/finance/strategic/services/strategic_finance_service.py")
    assert "from core.finance.strategic.services.strategic_finance_payload import" in strategic
    assert "payload = build_decision_payload(" in strategic

    executor = _read("runtime/executor.py")
    assert "runtime.executor_runtime_support" in executor
    assert "from runtime.executor_recovery_flow import execute_recovery_flow, has_proof_event" in executor
    assert "execute_recovery_flow(" in executor

    support = _read("runtime/executor_runtime_support.py")
    assert "from runtime.executor_effects import build_runtime_executor_effects" in support
    assert "build_runtime_executor_effects(" in support

    ads_rl = _read("core/growth/ads/rl/service.py")
    assert "from .state_builder import build_state_from_ads_metrics" in ads_rl
    assert "from .plan_builder import to_ads_plan" in ads_rl
    assert "return build_state_from_ads_metrics(" in ads_rl
    assert "return to_ads_plan(" in ads_rl

    autopilot = _read("core/growth/autopilot_engine.py")
    assert "from core.growth.autopilot_engine_run import run_autopilot_engine" in autopilot
    assert "return await run_autopilot_engine(" in autopilot

    connector_shared = _read("interfaces/ads/connector_shared.py")
    assert "from .connector_value_coercion import" in connector_shared
    assert "def as_int(" not in connector_shared
    assert "def safe_ratio(" not in connector_shared

    apply_engine = _read("core/ads/apply_engine.py")
    assert "from core.ads.apply_engine_prechecks import (" in apply_engine
    assert "from core.ads.apply_engine_execution import build_dry_run_result, perform_apply_flow" in apply_engine
    assert "evaluate_gate_and_feedback(" in apply_engine
    assert "perform_apply_flow(" in apply_engine
    assert "build_dry_run_result(" in apply_engine

    for rel in [
        "core/ads/apply_engine_prechecks.py",
        "core/ads/apply_engine_execution.py",
    ]:
        path = ROOT / rel
        assert path.exists(), rel
        assert path.read_text(encoding="utf-8").strip(), rel
