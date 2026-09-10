from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "frontend" / "src"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_diagnosis_next_steps_reuse_canonical_decisioncore_and_existing_surfaces() -> None:
    panel = _read("BusinessIntelligencePanel.jsx")
    app = _read("App.jsx")
    model = _read("intelligenceNextSteps.js")
    assert "buildIntelligenceNextSteps(diagnosis.reasons || [])" in panel
    assert "Разобрать с DecisionCore" in panel
    assert "существующему DecisionCore в режиме советника" in panel
    assert "onRunGoal(clean)" in panel
    assert 'meta: { source: "owner_workspace" }' in app
    assert "onOpenSurface={openWorkspaceSection}" in app
    assert all(target in model for target in ("acquisition-planner-title", "business-customers-title", "business-operations-title"))


def test_next_steps_are_presentation_only_and_cannot_execute_or_relax_safety() -> None:
    model = _read("intelligenceNextSteps.js")
    panel = _read("BusinessIntelligencePanel.jsx")
    assert "Нажатие «Разобрать»" in panel
    assert "не отправляет сообщения, не меняет рекламу и не тратит деньги" in panel
    assert all(token not in model for token in ("fetch(", "/actions/execute", "autonomy_tier", "provider_key", "dispatch(", "execute("))
    assert "no_major_issues_detected" not in model
    assert "slice(0, 3)" in model


def test_next_steps_cover_current_actionable_analytics_diagnoses() -> None:
    model = _read("intelligenceNextSteps.js")
    for reason in ("low_offer_ctr", "low_retention", "high_blocked_decision_ratio", "latency_degraded", "latency_critical", "low_revenue_signal"):
        assert f"{reason}:" in model
    assert "Почему сейчас" in _read("BusinessIntelligencePanel.jsx")
