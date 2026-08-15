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
    return {"run_id": run_id, "idempotency_key": f"post-deploy-{run_id}",
            "action_id": f"post-deploy-action-{run_id}", "offer_id": f"post-deploy-offer-{run_id}"}


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
        return fetch_json(f"{base}{path}", method=method, headers=headers, payload=payload, timeout=10)

    status, health = call("/health")
    assert status == 200 and str(health.get("status")).lower() in {"ok", "degraded"}
    status, ready = call("/readyz")
    assert status == 200 and str(ready.get("status")).lower() == "ready"
    status, tenants = call("/control-plane/admin/tenants")
    assert status == 200 and "tenants" in tenants
    status, result = call("/actions/execute", "POST", {"action_type": "pricing.publish_offer",
                          "payload": {"offer_id": ids["offer_id"], "amount": 199}})
    assert status == 200 and str(result.get("status") or "").lower() not in {"error", "failed"}
    status, audit = call("/control-plane/audit/actions")
    assert status == 200 and "records" in audit
    return {**ids, "tenant_id": tenant_id}


def main() -> int:
    result = run_smoke_flow()
    print(f"SMOKE_FLOW_OK run_id={result['run_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
