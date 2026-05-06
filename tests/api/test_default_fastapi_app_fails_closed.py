from __future__ import annotations

from fastapi.testclient import TestClient

from entrypoints.api.fastapi_app_factory import create_app


def test_default_fastapi_app_execute_action_fails_closed_without_runtime_service(monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_API_IDEMPOTENCY_PATH", ":memory:")
    client = TestClient(create_app())

    response = client.post("/actions/execute", json={"action_type": "launch", "payload": {"x": 1}})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["action_type"] == "launch"
    assert payload["reason"] == "runtime_application_service_not_wired"
