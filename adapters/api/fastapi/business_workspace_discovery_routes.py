from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from application.business_discovery import (
    BusinessDiscoveryWorkspace,
    OwnerBusinessAssertion,
)

CANON_BUSINESS_WORKSPACE_DISCOVERY_ROUTES = True
_ALLOWED_ASSERTION_KEYS = frozenset(
    {
        "field_key",
        "value",
        "unknown",
        "observed_at_ms",
        "occurred_at_ms",
        "correlation_id",
    }
)


def _idempotency_key(request: Request) -> str:
    return str(
        request.headers.get("x-idempotency-key")
        or request.headers.get("idempotency-key")
        or ""
    ).strip()


def _actor_id(principal: object) -> str:
    actor = str(
        getattr(principal, "actor_id", None)
        or getattr(principal, "subject_id", None)
        or getattr(principal, "subject", None)
        or ""
    ).strip()
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="owner_actor_identity_required",
        )
    return actor


def _optional_int(body: Mapping[str, Any], key: str) -> int | None:
    if key not in body or body[key] is None:
        return None
    value = body[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{key}_must_be_integer",
        )
    return int(value)


def register_business_workspace_discovery_routes(
    *,
    router: APIRouter,
    auth_bundle,
    workspace: BusinessDiscoveryWorkspace,
) -> None:
    @router.get("/business-workspace/discovery", tags=["business-workspace"])
    async def discovery_workspace(request: Request) -> dict[str, Any]:
        _, tenant_id, business_id = business_owner_scope(
            request=request,
            auth_bundle=auth_bundle,
            required_scope="provider_control_plane",
        )
        return workspace.describe(tenant_id=tenant_id, business_id=business_id)

    @router.post("/business-workspace/discovery/assertions", tags=["business-workspace"])
    async def record_discovery_assertion(request: Request) -> dict[str, Any]:
        principal, tenant_id, business_id = business_owner_scope(
            request=request,
            auth_bundle=auth_bundle,
            required_scope="provider_control_plane",
        )
        body = await json_body(request)
        extra = set(body).difference(_ALLOWED_ASSERTION_KEYS)
        if extra:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="business_discovery_unknown_request_fields",
            )
        key = _idempotency_key(request)
        if not key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="idempotency_key_required",
            )
        if "unknown" in body and not isinstance(body["unknown"], bool):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="unknown_must_be_boolean",
            )
        observed_at_ms = _optional_int(body, "observed_at_ms")
        if observed_at_ms is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="observed_at_ms_required",
            )
        assertion = OwnerBusinessAssertion(
            tenant_id=tenant_id,
            business_id=business_id,
            actor_id=_actor_id(principal),
            field_key=str(body.get("field_key") or ""),
            value=body.get("value"),
            observed_at_ms=observed_at_ms,
            occurred_at_ms=_optional_int(body, "occurred_at_ms"),
            unknown=bool(body.get("unknown", False)),
            correlation_id=(
                None
                if body.get("correlation_id") is None
                else str(body.get("correlation_id") or "").strip() or None
            ),
        )
        try:
            return workspace.assert_owner(
                assertion=assertion,
                idempotency_key=key,
                recorded_at_ms=int(time.time() * 1000),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            detail = str(exc)
            if detail == "STATE_SNAPSHOT_CONCURRENT_UPDATE":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="business_discovery_concurrent_update",
                ) from exc
            raise


__all__ = [
    "CANON_BUSINESS_WORKSPACE_DISCOVERY_ROUTES",
    "register_business_workspace_discovery_routes",
]
