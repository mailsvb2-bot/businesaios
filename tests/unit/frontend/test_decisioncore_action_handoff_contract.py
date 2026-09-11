from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "frontend" / "src"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_decisioncore_handoff_projects_server_verified_draft_into_existing_action_center() -> None:
    app = _read("App.jsx")
    panel = _read("BusinessIntelligencePanel.jsx")
    assert "/business-workspace/decision-draft" in app
    assert "run_id: goalResult.run_id, decision_id: step.decision_id, action_id: step.action_id" in app
    assert "onPrepareAction={prepareDecisionAction}" in app
    assert 'goalStep?.action === "send_message@v1"' in panel
    assert "Передать как черновик в Центр действий" in panel
    assert "серверным ledger" in panel
    assert "Черновик из DecisionCore" in app
    assert 'source: "owner_decision_draft"' in app
    assert "source_run_id" in app and "source_decision_id" in app and "source_action_id" in app


def test_handoff_does_not_create_second_execution_path_or_relax_owner_safety() -> None:
    app = _read("App.jsx")
    panel = _read("BusinessIntelligencePanel.jsx")
    assert app.count('action_type: "send_message@v1"') == 1
    assert 'const outcome = await runOperation("message_send", actionExecuteUrl' in app
    assert "/control-plane/provider-runtime/approval-resume" in app
    assert "Подтвердить и выполнить" in app
    assert "execution_allowed" not in panel
    assert "autonomy_tier" not in app
    assert "/actions/execute" not in panel
    assert "Ничего не отправлено и approval не создан" in panel


def test_unknown_decisioncore_recipient_requires_customer_selection_instead_of_placeholder() -> None:
    app = _read("App.jsx")
    assert "BusinessAIOS не подставляет неизвестный адресат" in app
    assert "Выбрать клиента" in app
    assert "customerMatches.length === 1" in app


def test_action_center_shows_server_linked_decisioncore_result_without_overclaiming_delivery() -> None:
    app = _read("App.jsx")
    assert "operationDecisionProvenance" in app
    assert "Результат связан с решением DecisionCore" in app
    assert "Сервер подтвердил происхождение" in app
    assert "не объявляется доказанной доставкой получателю" in app
    assert "decision_provenance" in app
