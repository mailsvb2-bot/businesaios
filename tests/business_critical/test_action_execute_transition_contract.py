from __future__ import annotations

from fastapi.testclient import TestClient

from entrypoints.api.fastapi_app_factory import create_app


def test_actions_execute_fails_closed_when_runtime_not_wired() -> None:
    client = TestClient(create_app())

    response = client.post("/actions/execute", json={"action_type": "send_email", "payload": {"to": "nobody@example.invalid"}})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "blocked"
    assert body["action_type"] == "send_email"
    assert body["reason"] == "runtime_application_service_not_wired"
    assert body["details"] == {}
    assert body["capability_view"] == {}


def test_actions_execute_does_not_require_decision_core_direct_decide_and_execute() -> None:
    from core.ai.decision_core import DecisionCore

    # DecisionCore remains the decision owner. The public API transition must not
    # require the raw core object to expose a transport/runtime method named
    # decide_and_execute. Execution wiring belongs to the runtime application
    # service/dispatcher boundary, not to a second DecisionCore surface.
    assert hasattr(DecisionCore, "decide")
    assert not hasattr(DecisionCore, "decide_and_execute")


def test_fail_closed_readiness_surfaces_exist_without_runtime_wiring() -> None:
    client = TestClient(create_app())

    for path in ("/readyz", "/storagez", "/executionz"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["mode"] == "fails_closed"
        assert body["runtime_wired"] is False
        assert body["reason"] == "runtime_application_service_not_wired"
