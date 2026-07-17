from __future__ import annotations

from application.decision.decision_service import DecisionService
from core.constraints.decision import DecisionConstraints
from kernel.decision_candidate import DecisionCandidate
from kernel.decision_request import DecisionRequest
from orchestration.decision_pipeline import DecisionPipeline


class _Selector:
    def select(self, candidates):
        return max(candidates, key=lambda item: item.score) if candidates else None


class _Validator:
    def validate(self, candidate, constraints):
        del constraints
        return (candidate.score >= 0.0, "negative_score")


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


def test_public_decision_pipeline_preserves_recommendation_functionality() -> None:
    publisher = _Publisher()
    history = _History()
    service = DecisionService(
        selector=_Selector(),
        validator=_Validator(),
        publisher=publisher,
        history=history,
    )
    pipeline = DecisionPipeline(service)
    candidates = [
        DecisionCandidate(
            action_type="send_message",
            channel="telegram",
            score=0.4,
            expected_value=0.4,
            confidence=1.0,
            payload={"text": "first"},
            candidate_id="candidate-a",
        ),
        DecisionCandidate(
            action_type="send_message",
            channel="whatsapp",
            score=0.9,
            expected_value=0.9,
            confidence=1.0,
            payload={"text": "second"},
            candidate_id="candidate-b",
        ),
    ]

    result, audit = pipeline.run(
        candidates,
        constraints={},
        request=DecisionRequest(
            business_id="business-1",
            objective=DecisionConstraints().objective_name,
            input_bundle_id="bundle-1",
            request_id="request-1",
        ),
    )

    assert audit is not None
    assert result.approved is True
    assert result.recommended is True
    assert result.candidate is candidates[1]
    assert result.executable_action is None
    assert result.trace.steps == [
        "decision_space_received",
        "decision_space_validated",
        "recommendation_emitted",
    ]
    assert publisher.results == [result]
    assert history.results == [result]
