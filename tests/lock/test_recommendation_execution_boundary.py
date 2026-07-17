from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from application.decision.action_dispatcher import (
    ActionDispatcher,
    DecisionEnvelopeRequiredError,
)
from application.decision.decision_service import (
    DecisionApplicationService,
    DecisionService,
)
from contracts.executable_action import ExecutableAction
from core.constraints.decision import DecisionConstraints
from kernel.decision_candidate import DecisionCandidate
from kernel.decision_request import DecisionRequest
from kernel.decision_space import DecisionSpace

ROOT = Path(__file__).resolve().parents[2]


class _Selector:
    def select(self, candidates):
        return candidates[0] if candidates else None


class _Validator:
    def validate(self, candidate, constraints):
        del candidate, constraints
        return True, "ok"


class _Publisher:
    def __init__(self) -> None:
        self.results = []

    def publish(self, result) -> None:
        self.results.append(result)


class _History:
    def __init__(self) -> None:
        self.results = []

    def append(self, result) -> None:
        self.results.append(result)


class _ExecutionPort:
    def __init__(self) -> None:
        self.envelopes = []

    def execute(self, envelope):
        self.envelopes.append(envelope)
        return {"ok": True}


class _Observability:
    def audit_events(self) -> tuple[str, ...]:
        return ("audit",)


@pytest.mark.lock
def test_recommendation_service_has_no_decision_issuance_aliases() -> None:
    for name in ("issue", "optimize", "decide"):
        assert name not in DecisionService.__dict__
    assert DecisionService.PRODUCES_EXECUTABLE_ACTION is False


@pytest.mark.lock
def test_recommendation_preserves_selection_without_executable_authority() -> None:
    publisher = _Publisher()
    history = _History()
    service = DecisionService(
        selector=_Selector(),
        validator=_Validator(),
        publisher=publisher,
        history=history,
    )
    candidate = DecisionCandidate(
        action_type="send_message",
        channel="telegram",
        score=1.0,
        expected_value=1.0,
        confidence=1.0,
        payload={"text": "hello"},
        candidate_id="candidate-1",
    )

    result, audit = service.select_action(
        DecisionSpace(candidates=[candidate]),
        DecisionConstraints(),
        DecisionRequest(
            business_id="business-1",
            objective="profit_adjusted_growth",
            input_bundle_id="bundle-1",
            request_id="request-1",
        ),
    )

    assert audit is not None
    assert result.candidate is candidate
    assert result.recommended is True
    assert result.approved is True
    assert result.executable_action is None
    assert result.as_dict()["executable"] is False
    assert result.trace.steps[-1] == "recommendation_emitted"
    assert publisher.results == [result]
    assert history.results == [result]


@pytest.mark.lock
def test_application_execution_accepts_only_signed_envelopes() -> None:
    port = _ExecutionPort()
    service = DecisionApplicationService(
        decision_execution_port=port,
        observability_port=_Observability(),
    )
    envelope = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="noop@v1",
        )
    )

    assert service.execute_action(envelope) == {"ok": True}
    assert port.envelopes == [envelope]
    assert service.startup_audit_events() == ("audit",)

    legacy_action = ExecutableAction(
        action_id="action-1",
        action_type="send_message",
        channel="telegram",
        payload={"text": "blocked"},
        decision_id="unverified-decision",
        correlation_id="correlation-2",
    )
    with pytest.raises(
        DecisionEnvelopeRequiredError,
        match="DecisionEnvelope required",
    ):
        service.execute_action(legacy_action)


@pytest.mark.lock
def test_dispatcher_source_contains_no_decide_and_execute_shortcut() -> None:
    assert "decide_and_execute" not in ActionDispatcher.__dict__

    path = ROOT / "application/decision/action_dispatcher.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    forbidden = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "decide_and_execute"
    ]
    assert forbidden == []


@pytest.mark.lock
def test_production_tree_contains_no_combined_decision_execution_shortcut() -> None:
    offenders: list[str] = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("tests/"):
            continue
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=relative,
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name in {
                    "decide_and_execute",
                    "build_executable_action",
                    "build_executable_action_payload",
                }:
                    offenders.append(f"{relative}:{node.lineno}:{node.name}")
            elif isinstance(node, ast.Attribute):
                if node.attr == "decide_and_execute":
                    offenders.append(
                        f"{relative}:{node.lineno}:decide_and_execute"
                    )
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in {
                        "build_executable_action",
                        "build_executable_action_payload",
                    }:
                        offenders.append(
                            f"{relative}:{node.lineno}:{alias.name}"
                        )

    assert offenders == [], (
        "combined decision/execution authority remains: "
        + ", ".join(sorted(offenders))
    )


@pytest.mark.lock
def test_recommendation_source_builds_no_executable_action() -> None:
    paths = (
        ROOT / "application/decision/decision_service.py",
        ROOT / "application/decision/decision_contract.py",
    )
    offenders: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in (
            "build_executable_action(",
            "executable_action_emitted",
            "decide_and_execute",
        ):
            if token in text:
                offenders.append(f"{path.as_posix()}:{token}")

    assert offenders == []
