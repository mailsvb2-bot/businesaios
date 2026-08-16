from __future__ import annotations

import os
import uuid

from scripts.ci.http_probe_io import fetch_json

CANON_SERVER_SMOKE_FLOW = True


def _required_env(name: str, forbidden: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value == forbidden:
        raise RuntimeError(f"unsafe or missing production setting: {name}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def build_smoke_identity() -> dict[str, str]:
    run_id = uuid.uuid4().hex
    return {"run_id": run_id, "idempotency_key": f"post-deploy-{run_id}", "action_id": f"post-deploy-action-{run_id}", "offer_id": f"post-deploy-offer-{run_id}"}


def run_smoke_flow() -> dict[str, str]:
    api_key = _required_env("CONTROL_PLANE_API_KEY", "development-control-plane-key")
    tenant_id = _required_env("SMOKE_TENANT_ID", "default-business")
    ids = build_smoke_identity()
    base = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

    def call(path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
        headers = {"x-api-key": api_key}
        if method == "POST":
            headers.update({"content-type": "application/json", "x-tenant-id": tenant_id, "x-idempotency-key": ids["idempotency_key"], "x-action-id": ids["action_id"]})
        return fetch_json(f"{base}{path}", method=method, headers=headers, payload=payload, timeout=10, follow_redirects=False)

    status, health = call("/health")
    _require(status == 200 and str(health.get("status")).lower() in {"ok", "degraded"}, "synthetic health check failed")
    status, ready = call("/readyz")
    _require(status == 200 and str(ready.get("status")).lower() == "ready", "synthetic readiness check failed")
    status, tenants = call("/control-plane/admin/tenants")
    _require(status == 200 and "tenants" in tenants, "synthetic tenant control-plane check failed")
    status, result = call("/actions/execute", "POST", {"action_type": "pricing.publish_offer", "payload": {"offer_id": ids["offer_id"], "amount": 199}})
    action_status = str(result.get("status") or "").strip().lower()
    _require(status == 200 and bool(action_status) and action_status not in {"error", "failed"}, f"synthetic action failed: http_status={status} action_status={action_status!r}")
    status, audit = call("/control-plane/audit/actions")
    _require(status == 200 and any(str(item.get("action_id") or "") == ids["action_id"] for item in audit.get("records", [])), "synthetic action audit correlation failed")
    return {**ids, "tenant_id": tenant_id, "action_status": action_status}


def main() -> int:
    result = run_smoke_flow()
    print(f"SMOKE_FLOW_OK run_id={result['run_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
