from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import time

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


def _request(port: int, path: str, *, method: str = "GET", headers: dict | None = None, payload: dict | None = None) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = dict(headers or {})
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw}
        return response.status, data
    finally:
        connection.close()


def _wait_until_healthy(port: int, process: subprocess.Popen, log_path) -> None:
    deadline, last_error = time.monotonic() + 40, ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"canonical API process exited early ({process.returncode})\n{_log_tail(log_path)}")
        try:
            status, payload = _request(port, "/health")
            if status == 200:
                return
            last_error = f"HTTP {status}: {payload!r}"[:1000]
        except (OSError, http.client.HTTPException) as exc:
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
            "FORWARDED_ALLOW_IPS": "203.0.113.254",
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
            _wait_until_healthy(port, process, log_path)
            status, insecure_marketplace = _request(port, "/public-site/integrations")
            assert status == 403, insecure_marketplace
            assert insecure_marketplace["detail"] == "compliance_failed"

            secure_headers = {"X-Forwarded-Proto": "https"}
            status, marketplace = _request(port, "/public-site/integrations", headers=secure_headers)
            assert status == 200, marketplace
            assert marketplace["ok"] is True
            assert marketplace["policy"]["write_actions_enabled"] is False
            selectable = next((item for item in marketplace["items"] if item.get("selectable") is True), None)
            assert selectable is not None, "public marketplace has no customer-selectable read-only provider"
            provider_key = selectable["provider_key"]

            status, anonymous_workspace = _request(port, "/business-workspace/providers", headers=secure_headers)
            assert status == 401, anonymous_workspace
            assert anonymous_workspace["detail"] == "missing_authentication"

            status, cta = _request(
                port,
                "/public-site/cta/start",
                method="POST",
                headers=secure_headers,
                payload={
                    "business_name": "Canonical API E2E Business",
                    "industry": "services",
                    "city": "Amsterdam",
                    "goal": "growth",
                    "selected_providers": [provider_key],
                    "autonomy_mode": "advisor",
                },
            )
            assert status == 200, cta
            owner = cta.get("owner_session") or {}
            assert cta["ok"] is True
            assert cta["write_actions_enabled"] is False
            assert cta["approval_required_before_execution"] is True
            assert owner.get("storage") == "session_only"
            assert owner.get("tenant_id") == cta["tenant_id"]
            assert owner.get("business_id") == cta["business_id"]
            assert isinstance(owner.get("api_key"), str) and "." in owner["api_key"]
            assert cta["selected_providers"] == [provider_key]

            status, status_payload = _request(port, f"/public-site/cta/{cta['intake_id']}", headers=secure_headers)
            assert status == 200, status_payload
            assert status_payload["found"] is True
            assert status_payload["tenant_id"] == cta["tenant_id"]
            assert status_payload["business_id"] == cta["business_id"]
            assert status_payload["selected_providers"] == [provider_key]

            status, workspace = _request(
                port,
                "/business-workspace/providers",
                headers={**secure_headers, "X-API-Key": owner["api_key"]},
            )
            assert status == 200, workspace
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
