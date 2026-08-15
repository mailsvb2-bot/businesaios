from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.server import smoke_flow

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERIFY = PROJECT_ROOT / "scripts" / "server" / "verify_runtime_host_contract.sh"
EXPECTED_SHA = "a" * 40


def _run_verify(tmp_path: Path, **extra_env: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ.get("PATH", ""), "EXPECTED_SHA": EXPECTED_SHA,
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
                  "runtime_orchestrator_present", "synthetic_flow", "PRODUCTION_VERDICT_PATH"):
        assert token in text
    assert "development-control-plane-key" in text
    assert "default-business" in text
    assert "observed SHA" in text and "does not match expected SHA" in text


def test_expected_sha_is_mandatory_before_any_host_probe(tmp_path: Path) -> None:
    env = {"PATH": os.environ.get("PATH", ""), "PRODUCTION_VERDICT_PATH": str(tmp_path / "verdict.json")}
    result = subprocess.run(["bash", str(VERIFY)], cwd=PROJECT_ROOT, env=env,
                            text=True, capture_output=True, check=False)
    assert result.returncode != 0
    assert "EXPECTED_SHA must be a full 40-character git SHA" in result.stderr
    assert not (tmp_path / "verdict.json").exists()


def test_development_control_key_fails_and_writes_sha_bound_verdict(tmp_path: Path) -> None:
    result = _run_verify(tmp_path, APP_ENV="prod", CONTROL_PLANE_API_KEY="development-control-plane-key",
                         SMOKE_TENANT_ID="production-smoke", DATABASE_URL="postgresql://invalid/db")
    assert result.returncode != 0
    payload = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "fail"
    assert payload["expected_sha"] == EXPECTED_SHA
    assert payload["checks"]["production_credentials"]["status"] == "fail"


def test_smoke_tenant_and_ids_are_fail_closed_and_unique(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMOKE_TENANT_ID", "default-business")
    with pytest.raises(RuntimeError, match="SMOKE_TENANT_ID"):
        smoke_flow._required_env("SMOKE_TENANT_ID", "default-business")
    first = smoke_flow.build_smoke_identity()
    second = smoke_flow.build_smoke_identity()
    for key in ("run_id", "idempotency_key", "action_id", "offer_id"):
        assert first[key] != second[key]
