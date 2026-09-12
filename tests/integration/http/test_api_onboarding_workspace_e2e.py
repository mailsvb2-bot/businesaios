from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import time
from http.cookies import SimpleCookie

from scripts.ci.paths import repo_root


_HTTP_REQUEST_TIMEOUT_SECONDS = 15


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


def _request(port: int, path: str, *, method: str = "GET", headers: dict | None = None, payload: dict | None = None, cookies: dict[str, str] | None = None) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = dict(headers or {})
    if cookies:
        request_headers.setdefault("Cookie", "; ".join(f"{key}={value}" for key, value in cookies.items()))
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=_HTTP_REQUEST_TIMEOUT_SECONDS)
    try:
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8", errors="replace")
        if cookies is not None:
            for header, value in response.getheaders():
                if header.lower() != "set-cookie":
                    continue
                parsed = SimpleCookie()
                parsed.load(value)
                for key, morsel in parsed.items():
                    cookies[key] = morsel.value
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
            status, anonymous_businesses = _request(port, "/public-site/owner/businesses", headers=secure_headers)
            assert status == 401, anonymous_businesses
            assert anonymous_businesses["detail"] == "owner_account_session_required"

            browser_cookies: dict[str, str] = {}
            status, cta = _request(
                port,
                "/public-site/cta/start",
                method="POST",
                headers=secure_headers,
                cookies=browser_cookies,
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
            assert set(browser_cookies) >= {"businessaios_owner_account", "businessaios_owner_resume"}
            assert [item["business_id"] for item in cta["owner_businesses"]] == [cta["business_id"]]
            status, account_token_workspace = _request(
                port,
                "/business-workspace/providers",
                headers={**secure_headers, "X-API-Key": browser_cookies["businessaios_owner_account"]},
            )
            assert status == 403, account_token_workspace
            assert account_token_workspace["detail"] in {"ttl_exceeds_policy", "owner_business_scope_required"}

            status, second_cta = _request(
                port,
                "/public-site/cta/start",
                method="POST",
                headers=secure_headers,
                cookies=browser_cookies,
                payload={
                    "business_name": "Canonical Second Business",
                    "industry": "commerce",
                    "city": "Tallinn",
                    "goal": "sales",
                    "selected_providers": [provider_key],
                    "autonomy_mode": "advisor",
                },
            )
            assert status == 200, second_cta
            assert second_cta["tenant_id"] != cta["tenant_id"]
            assert second_cta["business_id"] != cta["business_id"]
            assert second_cta["user_id"] == cta["user_id"]
            assert {item["business_id"] for item in second_cta["owner_businesses"]} == {cta["business_id"], second_cta["business_id"]}

            status, business_list = _request(port, "/public-site/owner/businesses", headers=secure_headers, cookies=browser_cookies)
            assert status == 200, business_list
            assert {item["business_id"] for item in business_list["businesses"]} == {cta["business_id"], second_cta["business_id"]}

            status, switched_back = _request(port, f"/public-site/cta/{cta['intake_id']}", headers=secure_headers, cookies=browser_cookies)
            assert status == 200, switched_back
            switched_owner = switched_back.get("owner_session") or {}
            assert switched_owner.get("tenant_id") == cta["tenant_id"]
            assert switched_owner.get("business_id") == cta["business_id"]
            assert isinstance(switched_owner.get("api_key"), str) and "." in switched_owner["api_key"]
            assert {item["business_id"] for item in switched_back["owner_businesses"]} == {cta["business_id"], second_cta["business_id"]}

            status, status_payload = _request(port, f"/public-site/cta/{cta['intake_id']}", headers=secure_headers)
            assert status == 200, status_payload
            assert status_payload["found"] is True
            assert status_payload["tenant_id"] == cta["tenant_id"]
            assert status_payload["business_id"] == cta["business_id"]
            assert status_payload["selected_providers"] == [provider_key]

            status, stale_workspace = _request(
                port,
                "/business-workspace/providers",
                headers={**secure_headers, "X-API-Key": owner["api_key"]},
            )
            assert status == 401, stale_workspace
            assert stale_workspace["detail"] == "inactive_api_key"

            status, workspace = _request(
                port,
                "/business-workspace/providers",
                headers={**secure_headers, "X-API-Key": switched_owner["api_key"]},
            )
            assert status == 200, workspace
            assert workspace["scope_source"] == "authenticated_owner_session"
            assert workspace["write_actions_enabled"] is False
            chosen = next((item for item in workspace["providers"] if item["provider_key"] == provider_key), None)
            assert chosen is not None
            assert chosen["customer_selectable"] is True
            assert chosen["read_supported"] is True
            assert chosen["write_actions_enabled"] is False

            status, approvals = _request(
                port,
                "/control-plane/approvals/open",
                headers={**secure_headers, "X-API-Key": switched_owner["api_key"]},
            )
            assert status == 200, approvals
            assert approvals["tenant_id"] == cta["tenant_id"]
            assert approvals["records"] == []

            status, customers = _request(
                port,
                "/business-workspace/customers",
                headers={**secure_headers, "X-API-Key": switched_owner["api_key"]},
            )
            assert status == 200, customers
            assert customers["tenant_id"] == cta["tenant_id"]
            assert customers["business_id"] == cta["business_id"]
            assert customers["customers"] == []
            assert customers["count"] == 0

            owner_headers = {**secure_headers, "X-API-Key": switched_owner["api_key"]}
            status, invalid_window = _request(port, f"/analytics/dashboard/{cta['tenant_id']}?window_days=0", headers=owner_headers)
            assert status == 422, invalid_window
            status, oversized_window = _request(port, f"/analytics/dashboard/{cta['tenant_id']}?window_days=3651", headers=owner_headers)
            assert status == 422, oversized_window
            status, analytics = _request(port, f"/analytics/dashboard/{cta['tenant_id']}?window_days=30", headers=owner_headers)
            assert status == 200, analytics
            assert analytics["payload"]["dashboard"]["tenant_id"] == cta["tenant_id"]
            memory_scope = {"tenant_id": cta["tenant_id"], "business_id": cta["business_id"]}
            status, memory = _request(port, "/business-memory/summary", method="POST", headers=owner_headers, payload=memory_scope)
            assert status == 200, memory
            assert memory["business_id"] == cta["business_id"]
            status, recent = _request(port, "/business-memory/recent-runs", method="POST", headers=owner_headers, payload={**memory_scope, "limit": 5})
            assert status == 200, recent
            assert isinstance(recent["runs"], list)

            goal_payload = {"goal": "Increase repeat sales safely", "business_id": cta["business_id"], "tenant_id": cta["tenant_id"], "max_steps": 1, "profile": {"industry": "services"}, "meta": {"source": "owner_workspace"}}
            status, goal_without_key = _request(port, "/goals/execute", method="POST", headers=owner_headers, payload=goal_payload)
            assert status == 403, goal_without_key
            assert goal_without_key["detail"] == "api_replay_protection_required"
            status, goal_result = _request(port, "/goals/execute", method="POST", headers={**owner_headers, "X-Idempotency-Key": "owner-e2e-goal-1"}, payload=goal_payload)
            assert status == 200, goal_result
            assert goal_result["tenant_id"] == cta["tenant_id"]
            assert goal_result["business_id"] == cta["business_id"]
            assert goal_result["goal"] == goal_payload["goal"]
            assert len(goal_result["steps"]) <= 1
            status, memory_after_goal = _request(port, "/business-memory/summary", method="POST", headers=owner_headers, payload=memory_scope)
            assert status == 200, memory_after_goal
            assert memory_after_goal["total_runs"] >= memory["total_runs"] + 1
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
