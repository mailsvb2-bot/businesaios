from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from scripts.ci.http_probe_io import fetch_json

CANON_SERVER_SMOKE_FLOW = True
_FORBIDDEN_CONTROL_KEYS = {"development-control-plane-key"}
_FORBIDDEN_TENANTS = {"default-business"}


@dataclass(frozen=True)
class SmokeIdentity:
    run_id: str
    idempotency_key: str
    action_id: str
    offer_id: str


def _required_env(name: str, *, forbidden: set[str] | None = None) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"required production setting is missing: {name}")
    if forbidden and value in forbidden:
        raise RuntimeError(f"unsafe production setting for {name}")
    return value


def build_smoke_identity() -> SmokeIdentity:
    run_id = uuid.uuid4().hex
    return SmokeIdentity(
        run_id=run_id,
        idempotency_key=f"post-deploy-{run_id}",
        action_id=f"post-deploy-action-{run_id}",
        offer_id=f"post-deploy-offer-{run_id}",
    )


def _url(path: str) -> str:
    base = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{base}{path}"


def _get(path: str, *, api_key: str) -> tuple[int, dict]:
    return fetch_json(
        _url(path),
        method="GET",
        headers={"x-api-key": api_key},
        timeout=10,
    )


def _post(
    path: str,
    payload: dict,
    *,
    api_key: str,
    tenant_id: str,
    identity: SmokeIdentity,
) -> tuple[int, dict]:
    return fetch_json(
        _url(path),
        method="POST",
        headers={
            "content-type": "application/json",
            "x-tenant-id": tenant_id,
            "x-idempotency-key": identity.idempotency_key,
            "x-action-id": identity.action_id,
            "x-api-key": api_key,
        },
        payload=payload,
        timeout=10,
    )


def run_smoke_flow() -> dict[str, str]:
    api_key = _required_env("CONTROL_PLANE_API_KEY", forbidden=_FORBIDDEN_CONTROL_KEYS)
    tenant_id = _required_env("SMOKE_TENANT_ID", forbidden=_FORBIDDEN_TENANTS)
    identity = build_smoke_identity()

    status, health = _get("/health", api_key=api_key)
    assert status == 200 and str(health.get("status")).lower() in {"ok", "degraded"}
    status, ready = _get("/readyz", api_key=api_key)
    assert status == 200 and str(ready.get("status")).lower() == "ready"
    status, tenants = _get("/control-plane/admin/tenants", api_key=api_key)
    assert status == 200 and "tenants" in tenants
    status, result = _post(
        "/actions/execute",
        {
            "action_type": "pricing.publish_offer",
            "payload": {"offer_id": identity.offer_id, "amount": 199},
        },
        api_key=api_key,
        tenant_id=tenant_id,
        identity=identity,
    )
    assert status == 200 and str(result.get("status") or "").lower() not in {"error", "failed"}
    status, audit = _get("/control-plane/audit/actions", api_key=api_key)
    assert status == 200 and "records" in audit
    return {
        "run_id": identity.run_id,
        "idempotency_key": identity.idempotency_key,
        "action_id": identity.action_id,
        "offer_id": identity.offer_id,
        "tenant_id": tenant_id,
    }


def main() -> int:
    result = run_smoke_flow()
    print(f"SMOKE_FLOW_OK run_id={result['run_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
