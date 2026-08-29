from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.server import smoke_flow

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERIFY = PROJECT_ROOT / "scripts" / "server" / "verify_runtime_host_contract.sh"
EXPECTED_SHA = "a" * 40
CANONICAL_INGRESS_ENV = (
    "PUBLIC_BASE_URL=https://api.businessaios.ru\n"
    "BUSINESAIOS_TRUST_PROXY_HEADERS=true\n"
    "BUSINESAIOS_TRUSTED_PROXY_IPS=127.0.0.1/32,::1/128\n"
)
CANONICAL_RUNTIME_ENV = (
    "HEALTH_HOST=127.0.0.1\n"
    "WORKER_HEALTH_PORT=8087\n"
    "EVOLUTION_HEALTH_PORT=8087\n"
    "EVOLUTION_ENABLED=1\n"
)


def _run_verify(tmp_path: Path, *, env_text: str, **extra_env: str) -> subprocess.CompletedProcess[str]:
    deploy_root = tmp_path / "deploy"
    python_bin = deploy_root / ".venv" / "bin" / "python"
    python_bin.parent.mkdir(parents=True)
    python_bin.symlink_to(Path(sys.executable))
    env_file = tmp_path / "api.env"
    env_file.write_text(env_text, encoding="utf-8")
    env = {"PATH": os.environ.get("PATH", ""), "EXPECTED_SHA": EXPECTED_SHA,
           "BUSINESAIOS_DEPLOY_ROOT": str(deploy_root), "PRODUCTION_ENV_FILE": str(env_file),
           "PRODUCTION_VERDICT_PATH": str(tmp_path / "verdict.json"), **extra_env}
    return subprocess.run(["bash", str(VERIFY)], cwd=PROJECT_ROOT, env=env,
                          text=True, capture_output=True, check=False)


def test_verifier_is_single_existing_canonical_host_surface() -> None:
    assert VERIFY.exists()
    assert not (PROJECT_ROOT / "scripts" / "server" / "post_deploy_verify.py").exists()
    subprocess.run(["bash", "-n", str(VERIFY)], check=True)


def test_contract_contains_all_fail_closed_production_gates() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    for token in ("EXPECTED_SHA", "APP_ENV", "CONTROL_PLANE_API_KEY", "SMOKE_TENANT_ID",
                  "DATABASE_URL", "POSTGRES_DSN", "SELECT 1", "runtime_readiness",
                  "runtime_orchestrator_present", "synthetic_flow", "PRODUCTION_VERDICT_PATH",
                  "PUBLIC_BASE_URL", "BUSINESAIOS_TRUST_PROXY_HEADERS",
                  "BUSINESAIOS_TRUSTED_PROXY_IPS", "production_runtime_bindings",
                  "HEALTH_HOST", "WORKER_HEALTH_PORT", "EVOLUTION_HEALTH_PORT",
                  "EVOLUTION_ENABLED", "PUBLIC_APP_BASE", "public_app", "businesaios-public-app.html"):
        assert token in text
    assert "/etc/businesaios/api.env" in text
    assert '.venv/bin/python' in text and '"$PYTHON_BIN" -' in text
    assert "for cmd in curl git python" not in text
    assert "development-control-plane-key" in text
    assert "default-business" in text
    assert "observed SHA" in text and "does not match expected SHA" in text
    assert "unset CONTROL_PLANE_API_KEY SMOKE_TENANT_ID DATABASE_URL POSTGRES_DSN" in text


def test_expected_sha_is_mandatory_before_any_host_probe(tmp_path: Path) -> None:
    env = {"PATH": os.environ.get("PATH", ""), "PRODUCTION_VERDICT_PATH": str(tmp_path / "verdict.json")}
    result = subprocess.run(["bash", str(VERIFY)], cwd=PROJECT_ROOT, env=env,
                            text=True, capture_output=True, check=False)
    assert result.returncode != 0
    assert "EXPECTED_SHA must be a full 40-character git SHA" in result.stderr
    assert not (tmp_path / "verdict.json").exists()


def test_canonical_venv_python_is_mandatory(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(VERIFY)],
        cwd=PROJECT_ROOT,
        env={"PATH": os.environ.get("PATH", ""), "EXPECTED_SHA": EXPECTED_SHA,
             "BUSINESAIOS_DEPLOY_ROOT": str(tmp_path / "missing-deploy")},
        text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0
    assert "canonical production Python is missing or not executable" in result.stderr


def test_development_control_key_from_production_env_fails_and_writes_sha_bound_verdict(tmp_path: Path) -> None:
    result = _run_verify(
        tmp_path,
        env_text=(
            "APP_ENV=prod\n"
            + CANONICAL_INGRESS_ENV
            + CANONICAL_RUNTIME_ENV
            + "CONTROL_PLANE_API_KEY=development-control-plane-key\n"
            + "SMOKE_TENANT_ID=production-smoke\n"
            + "DATABASE_URL=postgresql://invalid/db\n"
        ),
    )
    assert result.returncode != 0
    payload = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "fail"
    assert payload["expected_sha"] == EXPECTED_SHA
    assert payload["checks"]["production_environment_file"]["status"] == "pass"
    assert payload["checks"]["production_ingress"]["status"] == "pass"
    assert payload["checks"]["production_runtime_bindings"]["status"] == "pass"
    assert payload["checks"]["production_credentials"]["status"] == "fail"


def test_unsafe_worker_health_bind_fails_before_credentials_or_host_probes(tmp_path: Path) -> None:
    result = _run_verify(
        tmp_path,
        env_text=(
            "APP_ENV=prod\n"
            + CANONICAL_INGRESS_ENV
            + CANONICAL_RUNTIME_ENV.replace("HEALTH_HOST=127.0.0.1", "HEALTH_HOST=0.0.0.0")
            + "CONTROL_PLANE_API_KEY=production-key\n"
            + "SMOKE_TENANT_ID=production-smoke\n"
            + "DATABASE_URL=postgresql://invalid/db\n"
        ),
    )
    assert result.returncode != 0
    payload = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "fail"
    assert payload["checks"]["production_ingress"]["status"] == "pass"
    assert payload["checks"]["production_runtime_bindings"]["status"] == "fail"
    assert "production_credentials" not in payload["checks"]
    assert "HEALTH_HOST must be 127.0.0.1" in result.stderr


def test_ambient_control_plane_values_cannot_replace_missing_production_env_values(tmp_path: Path) -> None:
    result = _run_verify(
        tmp_path,
        env_text=(
            "APP_ENV=prod\n"
            + CANONICAL_INGRESS_ENV
            + CANONICAL_RUNTIME_ENV
            + "DATABASE_URL=postgresql://invalid/db\n"
        ),
        CONTROL_PLANE_API_KEY="ambient-production-key",
        SMOKE_TENANT_ID="ambient-tenant",
    )
    assert result.returncode != 0
    payload = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert payload["checks"]["production_runtime_bindings"]["status"] == "pass"
    assert payload["checks"]["production_credentials"]["status"] == "fail"
    assert "required production setting is missing: CONTROL_PLANE_API_KEY" in result.stderr


def test_smoke_tenant_and_ids_are_fail_closed_and_unique(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMOKE_TENANT_ID", "default-business")
    with pytest.raises(RuntimeError, match="SMOKE_TENANT_ID"):
        smoke_flow._required_env("SMOKE_TENANT_ID", "default-business")
    first = smoke_flow.build_smoke_identity()
    second = smoke_flow.build_smoke_identity()
    for key in ("run_id", "idempotency_key", "action_id", "offer_id"):
        assert first[key] != second[key]


def test_smoke_requires_accepted_outcome_and_matching_action_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "production-key")
    monkeypatch.setenv("SMOKE_TENANT_ID", "production-smoke")

    blocked = iter([
        (200, {"status": "ok"}),
        (200, {"status": "ready"}),
        (200, {"tenants": []}),
        (200, {"status": "blocked"}),
    ])
    monkeypatch.setattr(smoke_flow, "fetch_json", lambda *args, **kwargs: next(blocked))
    with pytest.raises(RuntimeError, match="production synthetic action was not accepted"):
        smoke_flow.run_smoke_flow()

    wrong_audit = iter([
        (200, {"status": "ok"}),
        (200, {"status": "ready"}),
        (200, {"tenants": []}),
        (200, {"status": "accepted"}),
        (200, {"records": [{"action_id": "different-action"}]}),
    ])
    monkeypatch.setattr(smoke_flow, "fetch_json", lambda *args, **kwargs: next(wrong_audit))
    with pytest.raises(AssertionError):
        smoke_flow.run_smoke_flow()
