from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts.ci import http_probe_io
from scripts.server import smoke_flow

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_LIFECYCLE = PROJECT_ROOT / "scripts" / "server" / "bootstrap_and_verify_production.sh"
SMOKE_FLOW = PROJECT_ROOT / "scripts" / "server" / "smoke_flow.py"


def _prepare_smoke(
    monkeypatch: pytest.MonkeyPatch,
    *,
    action_http_status: int = 200,
    action_payload: dict | None = None,
    audit_records: list[dict] | None = None,
) -> tuple[dict[str, str], list[dict[str, object]]]:
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "production-key")
    monkeypatch.setenv("SMOKE_TENANT_ID", "production-smoke")
    monkeypatch.setenv("SMOKE_BASE_URL", "https://api.businessaios.ru")
    identity = {
        "run_id": "run",
        "idempotency_key": "idem",
        "action_id": "action",
        "offer_id": "offer",
    }
    responses = iter([
        (200, {"status": "ok"}),
        (200, {"status": "ready"}),
        (200, {"tenants": []}),
        (action_http_status, {"status": "completed"} if action_payload is None else action_payload),
        (200, {"records": [{"action_id": identity["action_id"]}] if audit_records is None else audit_records}),
    ])
    calls: list[dict[str, object]] = []

    def fake_fetch_json(*args: object, **kwargs: object) -> tuple[int, dict]:
        calls.append(dict(kwargs))
        return next(responses)

    monkeypatch.setattr(smoke_flow, "build_smoke_identity", lambda: identity)
    monkeypatch.setattr(smoke_flow, "fetch_json", fake_fetch_json)
    return identity, calls


def test_credential_bearing_smoke_accepts_domain_success_without_following_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, calls = _prepare_smoke(monkeypatch)

    result = smoke_flow.run_smoke_flow()

    assert result["action_status"] == "completed"
    assert len(calls) == 5
    assert all(call.get("follow_redirects") is False for call in calls)


@pytest.mark.parametrize(
    ("http_status", "payload"),
    [
        (503, {"status": "completed"}),
        (200, {}),
        (200, {"status": ""}),
        (200, {"status": "error"}),
        (200, {"status": "failed"}),
    ],
)
def test_synthetic_action_fails_closed_on_transport_or_domain_failure(
    monkeypatch: pytest.MonkeyPatch,
    http_status: int,
    payload: dict,
) -> None:
    _prepare_smoke(monkeypatch, action_http_status=http_status, action_payload=payload)

    with pytest.raises(RuntimeError, match="synthetic action failed"):
        smoke_flow.run_smoke_flow()


def test_synthetic_action_still_requires_exact_audit_correlation(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_smoke(monkeypatch, audit_records=[{"action_id": "different-action"}])

    with pytest.raises(RuntimeError, match="audit correlation failed"):
        smoke_flow.run_smoke_flow()


def test_production_smoke_uses_runtime_checks_not_python_assertions() -> None:
    tree = ast.parse(SMOKE_FLOW.read_text(encoding="utf-8"))

    assert not any(isinstance(node, ast.Assert) for node in ast.walk(tree))


def test_http_probe_can_disable_redirect_following(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Result:
        returncode = 0
        stdout = b"{}\n200"
        stderr = b""

    def fake_run(cmd: list[str], **kwargs: object) -> Result:
        captured["cmd"] = cmd
        return Result()

    monkeypatch.setattr(http_probe_io.subprocess, "run", fake_run)
    status, payload = http_probe_io.fetch_json(
        "https://api.businessaios.ru/health",
        headers={"x-api-key": "production-key"},
        follow_redirects=False,
    )

    assert status == 200
    assert payload == {}
    assert "-L" not in captured["cmd"]


def test_host_lifecycle_uses_one_overall_readiness_deadline() -> None:
    text = HOST_LIFECYCLE.read_text(encoding="utf-8")

    assert "command -v timeout" in text
    assert "timeout 60s bash -c" in text
    assert "within 60 seconds after restart" in text
