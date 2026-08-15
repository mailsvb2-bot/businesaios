from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.server import post_deploy_verify as verifier
from scripts.server import smoke_flow

EXPECTED_SHA = "a" * 40
OTHER_SHA = "b" * 40


def _production_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    verdict_path = tmp_path / "production-verdict.json"
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("EXPECTED_SHA", EXPECTED_SHA)
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "production-control-key")
    monkeypatch.setenv("SMOKE_TENANT_ID", "production-smoke-tenant")
    monkeypatch.setenv("DATABASE_URL", "postgresql://verification.invalid/businesaios")
    monkeypatch.setenv("PRODUCTION_VERDICT_PATH", str(verdict_path))
    return verdict_path


def test_expected_sha_is_mandatory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXPECTED_SHA", raising=False)
    with pytest.raises(verifier.VerificationError, match="EXPECTED_SHA"):
        verifier._expected_sha()


def test_control_plane_key_has_no_development_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "development-control-plane-key")
    with pytest.raises(verifier.VerificationError, match="unsafe production setting"):
        verifier._api_key()


def test_smoke_tenant_has_no_working_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMOKE_TENANT_ID", "default-business")
    with pytest.raises(verifier.VerificationError, match="unsafe production setting"):
        verifier._tenant_id()


def test_database_dsn_is_mandatory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    with pytest.raises(verifier.VerificationError, match="PostgreSQL DSN"):
        verifier._database_dsn()


def test_synthetic_ids_are_unique_per_run() -> None:
    first = smoke_flow.build_smoke_identity()
    second = smoke_flow.build_smoke_identity()
    assert first.run_id != second.run_id
    assert first.idempotency_key != second.idempotency_key
    assert first.action_id != second.action_id
    assert first.offer_id != second.offer_id


def test_sha_mismatch_fails_and_writes_sha_bound_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    verdict_path = _production_env(monkeypatch, tmp_path)
    monkeypatch.setattr(verifier, "_observed_sha", lambda: OTHER_SHA)

    with pytest.raises(verifier.VerificationError, match="does not match expected SHA"):
        verifier.run_verification()

    payload = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "fail"
    assert payload["expected_sha"] == EXPECTED_SHA
    assert payload["observed_sha"] == OTHER_SHA
    assert payload["checks"]["sha_match"]["status"] == "fail"


def test_success_requires_all_gates_and_writes_pass_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    verdict_path = _production_env(monkeypatch, tmp_path)
    monkeypatch.setattr(verifier, "_observed_sha", lambda: EXPECTED_SHA)

    health = {
        "status": "ok",
        "checks": [{"name": "runtime", "status": "pass"}],
        "runtime_orchestrator_present": True,
        "details": {"runtime_readiness": {"ready": True}},
    }
    ready = {"status": "ready", "checks": [{"name": "runtime", "status": "pass"}]}

    def fake_fetch(path: str, *, api_key: str) -> tuple[int, dict]:
        assert api_key == "production-control-key"
        if path == "/health":
            return 200, health
        if path == "/readyz":
            return 200, ready
        raise AssertionError(path)

    monkeypatch.setattr(verifier, "_fetch", fake_fetch)
    monkeypatch.setattr(
        verifier,
        "_validate_runtime",
        lambda payload: {"runtime_ready": payload["details"]["runtime_readiness"]["ready"]},
    )
    monkeypatch.setattr(verifier, "_check_postgres", lambda dsn: {"select_1": 1})
    monkeypatch.setattr(
        verifier,
        "run_smoke_flow",
        lambda: {
            "run_id": "unique-run",
            "idempotency_key": "unique-idempotency",
            "action_id": "unique-action",
            "offer_id": "unique-offer",
            "tenant_id": "production-smoke-tenant",
        },
    )

    result = verifier.run_verification()
    payload = json.loads(verdict_path.read_text(encoding="utf-8"))

    assert result["verdict"] == "pass"
    assert payload["expected_sha"] == EXPECTED_SHA
    assert payload["observed_sha"] == EXPECTED_SHA
    assert payload["synthetic_run_id"] == "unique-run"
    assert all(item["status"] == "pass" for item in payload["checks"].values())
    assert {"health", "readiness", "runtime", "postgresql", "synthetic_flow", "sha_match"} <= set(
        payload["checks"]
    )
