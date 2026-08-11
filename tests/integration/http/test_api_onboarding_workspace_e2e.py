from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import httpx

from scripts.ci.paths import repo_root


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _log_tail(path, limit: int = 12000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"<api log unavailable: {exc}>"
    return text[-limit:]


def _wait_until_healthy(client: httpx.Client, process: subprocess.Popen, log_path) -> None:
    deadline, last_error = time.monotonic() + 40, ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"canonical API process exited early ({process.returncode})\n{_log_tail(log_path)}")
        try:
            response = client.get("/health")
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}: {response.text[:1000]}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise AssertionError(f"canonical API did not become healthy: {last_error}\n{_log_tail(log_path)}")


def test_real_api_onboarding_issues_owner_session_and_opens_workspace(tmp_path) -> None:
    root, port = repo_root(), _free_port()
    log_path = tmp_path / "api-e2e.log"
    env = os.environ.copy()
    runtime_dir = tmp_path / "runtime"
    pythonpath = [str(root), env.get("PYTHONPATH", "")]
    env.update(
        {
            "APP_PROFILE": "api",
            "APP_ENV": "dev",
            "ENV": "dev",
            "API_HOST": "127.0.0.1",
            "API_PORT": str(port),
            "APP_RUNTIME_DATA_DIR": str(runtime_dir),
            "BUSINESAIOS_DATA_DIR": str(runtime_dir),
            "DATA_DIR": str(tmp_path / "data"),
            "BUSINESAIOS_API_KEY_STORE_PATH": str(tmp_path / "api_keys.json"),
            "BUSINESAIOS_TENANT_REGISTRY_PATH": str(tmp_path / "tenant_registry.json"),
            "API_CONTROL_PLANE_API_KEY_PEPPER": "canonical-api-e2e-pepper",
            "BUSINESAIOS_TRUST_PROXY_HEADERS": "1",
            "BUSINESAIOS_TRUSTED_PROXY_IPS": "127.0.0.1/32",
            "PYTHONPATH": os.pathsep.join(value for value in pythonpath if value),
        }
    )

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, str(root / "scripts" / "server" / "run_profile.py")],
            cwd=tmp_path,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            base_url = f"http://127.0.0.1:{port}"
            with httpx.Client(base_url=base_url, timeout=5.0) as direct_client:
                _wait_until_healthy(direct_client, process, log_path)
                insecure_marketplace = direct_client.get("/public-site/integrations")
                assert insecure_marketplace.status_code == 403, insecure_marketplace.text
                assert insecure_marketplace.json()["detail"] == "compliance_failed"

            with httpx.Client(
                base_url=base_url,
                timeout=5.0,
                headers={"X-Forwarded-Proto": "https"},
            ) as client:
                marketplace_response = client.get("/public-site/integrations")
                assert marketplace_response.status_code == 200, marketplace_response.text
                marketplace = marketplace_response.json()
                assert marketplace["ok"] is True
                assert marketplace["policy"]["write_actions_enabled"] is False
                selectable = next((item for item in marketplace["items"] if item.get("selectable") is True), None)
                assert selectable is not None, "public marketplace has no customer-selectable read-only provider"
                provider_key = selectable["provider_key"]

                anonymous_workspace = client.get("/business-workspace/providers")
                assert anonymous_workspace.status_code == 401, anonymous_workspace.text
                assert anonymous_workspace.json()["detail"] == "missing_authentication"

                cta_response = client.post(
                    "/public-site/cta/start",
                    json={
                        "business_name": "Canonical API E2E Business",
                        "industry": "services",
                        "city": "Amsterdam",
                        "goal": "growth",
                        "selected_providers": [provider_key],
                        "autonomy_mode": "advisor",
                    },
                )
                assert cta_response.status_code == 200, cta_response.text
                cta = cta_response.json()
                owner = cta.get("owner_session") or {}
                assert cta["ok"] is True
                assert cta["write_actions_enabled"] is False
                assert cta["approval_required_before_execution"] is True
                assert owner.get("storage") == "session_only"
                assert owner.get("tenant_id") == cta["tenant_id"]
                assert owner.get("business_id") == cta["business_id"]
                assert isinstance(owner.get("api_key"), str) and "." in owner["api_key"]
                assert cta["selected_providers"] == [provider_key]

                status_response = client.get(f"/public-site/cta/{cta['intake_id']}")
                assert status_response.status_code == 200, status_response.text
                status_payload = status_response.json()
                assert status_payload["found"] is True
                assert status_payload["tenant_id"] == cta["tenant_id"]
                assert status_payload["business_id"] == cta["business_id"]
                assert status_payload["selected_providers"] == [provider_key]

                workspace_response = client.get(
                    "/business-workspace/providers",
                    headers={"X-API-Key": owner["api_key"]},
                )
                assert workspace_response.status_code == 200, workspace_response.text
                workspace = workspace_response.json()
                assert workspace["scope_source"] == "authenticated_owner_session"
                assert workspace["write_actions_enabled"] is False
                chosen = next((item for item in workspace["providers"] if item["provider_key"] == provider_key), None)
                assert chosen is not None
                assert chosen["customer_selectable"] is True
                assert chosen["read_supported"] is True
                assert chosen["write_actions_enabled"] is False
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
