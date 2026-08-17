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
            headers.update({"content-type": "application/json", "x-tenant-id": tenant_id,
                            "x-idempotency-key": ids["idempotency_key"], "x-action-id": ids["action_id"]})
        return fetch_json(f"{base}{path}", method=method, headers=headers, payload=payload, timeout=10,
                          follow_redirects=False)

    status, health = call("/health")
    if status != 200 or str(health.get("status")).lower() not in {"ok", "degraded"}: raise AssertionError(f"synthetic health check failed: http_status={status} status={str(health.get('status') or '').lower()!r}")
    status, ready = call("/readyz")
    if status != 200 or str(ready.get("status")).lower() != "ready": raise AssertionError(f"synthetic readiness check failed: http_status={status} status={str(ready.get('status') or '').lower()!r}")
    status, tenants = call("/control-plane/admin/tenants")
    if status != 200 or "tenants" not in tenants: raise AssertionError(f"synthetic tenant control-plane check failed: http_status={status} detail={str(tenants.get('detail') or '')!r}")
    status, result = call("/actions/execute", "POST", {"action_type": "pricing.publish_offer", "payload": {"offer_id": ids["offer_id"], "amount": 199}})
    if status != 200 or str(result.get("status") or "").lower() != "accepted": raise RuntimeError(f"production synthetic action was not accepted: http_status={status} action_status={str(result.get('status') or '').lower()!r}")
    status, audit = call("/control-plane/audit/actions")
    if status != 200 or not any(str(item.get("action_id") or "") == ids["action_id"] for item in audit.get("records", [])): raise AssertionError(f"synthetic action audit correlation failed: http_status={status}")
    return {**ids, "tenant_id": tenant_id}


def main() -> int:
    result = run_smoke_flow()
    print(f"SMOKE_FLOW_OK run_id={result['run_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
