from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    "execution/channel_roi_memory.py",
    "execution/roi_confidence_model.py",
    "execution/adaptive_roi_model.py",
    "execution/cac_learning_engine.py",
    "execution/business_roi_registry.py",
    "execution/capital_allocation_policy.py",
    "execution/portfolio_allocator.py",
    "execution/capital_rebalancer.py",
    "execution/roi_predictor.py",
    "execution/economic_simulator.py",
    "execution/survival_hysteresis.py",
    "execution/pre_action_economic_forecast.py",
]
FORBIDDEN = [
    "class DecisionCore",
    "RuntimeDecisionCore",
    "def decide(",
    "def issue(",
    "from core.ai.decision_core import DecisionCore",
    "from core.decision_core import DecisionCore",
]


def test_economic_luxury_modules_do_not_create_second_brain() -> None:
    for rel in TARGETS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in text, f"{rel} contains forbidden token: {token}"
