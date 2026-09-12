from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta

from scripts.ci.paths import repo_root
from tests.integration.http.test_api_onboarding_workspace_e2e import (
    _free_port,
    _request,
    _wait_until_healthy,
)


def test_owner_process_discovery_roundtrip_is_idempotent_and_fail_closed(tmp_path) -> None:
    root, port = repo_root(), _free_port()
    log_path = tmp_path / "api-process-e2e.log"
    runtime_dir = tmp_path / "runtime"
    env = os.environ.copy()
    env.update({
        "APP_PROFILE": "api", "APP_ENV": "dev", "ENV": "dev",
        "API_HOST": "127.0.0.1", "API_PORT": str(port),
        "APP_RUNTIME_DATA_DIR": str(runtime_dir), "BUSINESAIOS_DATA_DIR": str(runtime_dir),
        "DATA_DIR": str(tmp_path / "data"),
        "BUSINESAIOS_API_KEY_STORE_PATH": str(tmp_path / "api_keys.json"),
        "BUSINESAIOS_TENANT_REGISTRY_PATH": str(tmp_path / "tenant_registry.json"),
        "API_CONTROL_PLANE_API_KEY_PEPPER": "process-e2e-pepper",
        "FORWARDED_ALLOW_IPS": "203.0.113.254",
        "BUSINESAIOS_TRUST_PROXY_HEADERS": "1",
        "BUSINESAIOS_TRUSTED_PROXY_IPS": "127.0.0.1/32",
        "PYTHONPATH": os.pathsep.join(value for value in (str(root), env.get("PYTHONPATH", "")) if value),
    })
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, str(root / "scripts" / "server" / "run_profile.py")],
            cwd=tmp_path, env=env, stdout=log, stderr=subprocess.STDOUT, text=True,
        )
        try:
            _wait_until_healthy(port, process, log_path)
            secure = {"X-Forwarded-Proto": "https"}
            status, marketplace = _request(port, "/public-site/integrations", headers=secure)
            assert status == 200, marketplace
            provider_key = next(item["provider_key"] for item in marketplace["items"] if item.get("selectable") is True)
            status, cta = _request(
                port, "/public-site/cta/start", method="POST", headers=secure, cookies={},
                payload={
                    "business_name": "Process E2E", "industry": "services", "city": "Tallinn",
                    "goal": "operations", "selected_providers": [provider_key], "autonomy_mode": "advisor",
                },
            )
            assert status == 200, cta
            owner_headers = {**secure, "X-API-Key": cta["owner_session"]["api_key"]}
            now = datetime.now(UTC)
            recorded: list[dict] = []
            for index, days_ago in enumerate((8, 6, 4, 2, 0)):
                payload = {
                    "process_key": "client_followup",
                    "occurred_at": (now - timedelta(days=days_ago)).isoformat(),
                    "manual_minutes": 45,
                    "actor_cost_per_hour_minor": 50_000,
                    "direct_loss_minor": 1_000,
                    "revenue_at_risk_minor": 0,
                    "currency": "RUB",
                    "automation_fit": 0.9,
                    "operational_risk": 0.1,
                }
                key = f"process-fact-{index}"
                headers = {**owner_headers, "X-Idempotency-Key": key}
                status, result = _request(
                    port, "/business-workspace/process-observations",
                    method="POST", headers=headers, payload=payload,
                )
                assert status == 200, result
                recorded.append(result)
                if index == 0:
                    replay_status, replay = _request(
                        port, "/business-workspace/process-observations",
                        method="POST", headers=headers, payload=payload,
                    )
                    assert replay_status == 200 and replay == result
            assert len({item["evidence_id"] for item in recorded}) == 5
            status, discovery = _request(
                port, "/business-workspace/process-opportunities", headers=owner_headers,
            )
            assert status == 200, discovery
            assert len(discovery["opportunities"]) == 1
            opportunity = discovery["opportunities"][0]
            assert opportunity["money_status"] == "partial"
            build_payload = {
                "owner_goal": "Сократить ручной follow-up без обхода approval",
                "expected_coverage": 0.5,
            }
            build_headers = {**owner_headers, "X-Idempotency-Key": "process-build-1"}
            build_path = f"/business-workspace/process-opportunities/{opportunity['opportunity_id']}/blueprint"
            status, built = _request(
                port, build_path, method="POST", headers=build_headers, payload=build_payload,
            )
            assert status == 200, built
            assert built["execution_created"] is False
            assert built["blueprint"]["executable"] is False
            replay_status, built_replay = _request(
                port, build_path, method="POST", headers=build_headers, payload=build_payload,
            )
            assert replay_status == 200 and built_replay == built
            blueprint_id = built["blueprint"]["blueprint_id"]
            decision_path = f"/business-workspace/process-blueprints/{blueprint_id}/decision"
            decision_headers = {**owner_headers, "X-Idempotency-Key": "process-decision-1"}
            status, decision = _request(
                port, decision_path, method="POST", headers=decision_headers, payload={},
            )
            assert status == 200, decision
            assert decision["tenant_id"] == cta["tenant_id"]
            assert decision["business_id"] == cta["business_id"]
            replay_status, decision_replay = _request(
                port, decision_path, method="POST", headers=decision_headers, payload={},
            )
            assert replay_status == 200 and decision_replay == decision
            status, measurement = _request(
                port,
                f"/business-workspace/process-blueprints/{blueprint_id}/measurement",
                headers=owner_headers,
            )
            assert status == 200, measurement
            assert measurement["status"] == "intervention_not_verified"
            assert measurement["measurement_ready"] is False
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
