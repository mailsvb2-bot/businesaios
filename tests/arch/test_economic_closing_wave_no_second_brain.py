from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGETS = [
    "execution/action_cost_model.py",
    "execution/economic_signal_context.py",
    "execution/economic_memory_feedback.py",
    "observability/economic_trace_store.py",
    "observability/economic_metrics_stream.py",
]

FORBIDDEN_TOKENS = [
    "class DecisionCore",
    "RuntimeDecisionCore",
    "def decide(",
    "def issue(",
    "from core.ai.decision_core import DecisionCore",
    "from core.decision_core import DecisionCore",
]


def test_economic_closing_wave_modules_do_not_introduce_second_brain() -> None:
    for rel in TARGETS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in text, f"{rel} must not contain forbidden token: {token}"


def test_economic_signal_context_is_read_only_adapter() -> None:
    text = (ROOT / "execution/economic_signal_context.py").read_text(encoding="utf-8")
    assert "does not issue decisions" in text.lower()
    assert "does not route execution" in text.lower()
