from __future__ import annotations

import json
from pathlib import Path

from runtime.platform.production_readiness_admin_view import (
    PRODUCTION_READINESS_ARTIFACTS,
    build_production_readiness_admin_view,
)


def test_production_readiness_admin_view_exposes_required_artifacts(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts" / "ci"
    artifacts_dir.mkdir(parents=True)
    for name in PRODUCTION_READINESS_ARTIFACTS:
        (artifacts_dir / name).write_text(
            json.dumps({"artifact": name.removesuffix(".json"), "status": "advisory_only", "claims_production_ready": False}),
            encoding="utf-8",
        )

    view = build_production_readiness_admin_view(tmp_path)

    assert view["surface"] == "production_readiness"
    assert view["status"] == "observable"
    assert view["claims_production_ready"] is False
    for name in PRODUCTION_READINESS_ARTIFACTS:
        key = name.removesuffix(".json")
        assert view["artifacts"][key]["status"] == "advisory_only"
        assert view["artifacts"][key]["claims_production_ready"] is False


def test_production_readiness_admin_view_reports_missing_artifacts(tmp_path: Path) -> None:
    view = build_production_readiness_admin_view(tmp_path)

    assert view["claims_production_ready"] is False
    assert view["artifacts"]["postgres_contract"]["status"] == "missing"
    assert view["artifacts"]["postgres_migrations"]["status"] == "missing"
    assert view["artifacts"]["postgres_live"]["status"] == "missing"
    assert view["artifacts"]["production_boot"]["status"] == "missing"
    assert view["artifacts"]["container_runtime"]["status"] == "missing"


def test_admin_signing_preflight_is_redacted_and_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SAFETY_SIGNING_KEYS", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SAFETY_SIGNING_KEYS_JSON", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SAFETY_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("BUSINESAIOS_SIMULATION_EVIDENCE_SECRET", raising=False)
    blocked = build_production_readiness_admin_view(tmp_path)["signing_preflight"]
    assert blocked == {"status": "blocked", "reason": "production_signing_preflight_failed"}
    monkeypatch.setenv("BUSINESAIOS_SAFETY_SIGNING_SECRET", "unique-valid-safety-test-key")
    monkeypatch.setenv("BUSINESAIOS_SIMULATION_EVIDENCE_SECRET", "unique-valid-simulation-test-key")
    monkeypatch.delenv("BUSINESAIOS_SAFETY_ACTIVE_KEY_ID", raising=False)
    configured = build_production_readiness_admin_view(tmp_path)["signing_preflight"]
    assert configured == {"status": "configured"}
    assert "unique-valid" not in str(configured)
