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
_ALLOWED_GOAL_KEYS = frozenset(
    {
        "confirmed",
        "goal_id",
        "goal_kind",
        "target_key",
        "metric",
        "baseline",
        "target",
        "deadline_at_ms",
        "constraint_ids",
        "parent_goal_id",
        "priority",
    }
)
_ALLOWED_CONSTRAINT_KEYS = frozenset(
    {
        "confirmed",
        "constraint_id",
        "constraint_kind",
        "severity",
        "subject_type",
        "subject_id",
        "state_key",
        "comparison",
        "threshold",
    }
)
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
        principal, tenant_id, business_id = business_owner_scope(
            request=request,
            auth_bundle=auth_bundle,
            required_scope="provider_control_plane",
        )
        try:
            return workspace.describe(
                tenant_id=tenant_id,
                business_id=business_id,
                actor_id=_actor_id(principal),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    @router.post(
        "/business-workspace/discovery/provider-evidence/{evidence_id}/reconcile",
        tags=["business-workspace"],
    )
    async def reconcile_discovery_provider_evidence(
        request: Request,
        evidence_id: str,
    ) -> dict[str, Any]:
        _, tenant_id, business_id = business_owner_scope(
            request=request,
            auth_bundle=auth_bundle,
            required_scope="provider_control_plane",
        )
        try:
            return workspace.reconcile_provider_evidence(
                tenant_id=tenant_id,
                business_id=business_id,
                evidence_id=evidence_id,
            )
        except LookupError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="provider_evidence_not_found",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    @router.get("/business-workspace/discovery/goals", tags=["business-workspace"])
    async def discovery_goals(request: Request) -> dict[str, Any]:
        _, tenant_id, business_id = business_owner_scope(
            request=request,
            auth_bundle=auth_bundle,
            required_scope="provider_control_plane",
        )
        return {
            "tenant_id": tenant_id,
            "business_id": business_id,
            "goals": workspace.list_goals(tenant_id=tenant_id, business_id=business_id),
        }

    @router.post("/business-workspace/discovery/goals", tags=["business-workspace"])
    async def create_discovery_goal(request: Request) -> dict[str, Any]:
        principal, tenant_id, business_id = business_owner_scope(
            request=request,
            auth_bundle=auth_bundle,
            required_scope="provider_control_plane",
        )
        body = await json_body(request)
        extra = set(body).difference(_ALLOWED_GOAL_KEYS)
        if extra:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="business_discovery_unknown_goal_fields",
            )
        key = _idempotency_key(request)
        if not key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="idempotency_key_required",
            )
        confirmed = body.get("confirmed")
        if not isinstance(confirmed, bool):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="confirmed_must_be_boolean",
            )
        constraint_ids = body.get("constraint_ids") or ()
        if isinstance(constraint_ids, str) or not isinstance(constraint_ids, list | tuple):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="constraint_ids_must_be_array",
            )
        try:
            goal = workspace.create_goal(
                tenant_id=tenant_id,
                business_id=business_id,
                actor_id=_actor_id(principal),
                idempotency_key=key,
                confirmed=confirmed,
                goal_id=str(body.get("goal_id") or ""),
                goal_kind=str(body.get("goal_kind") or ""),
                target_key=body.get("target_key"),
                metric=body.get("metric"),
                baseline=body.get("baseline"),
                target=body.get("target"),
                deadline_at_ms=_optional_int(body, "deadline_at_ms"),
                constraint_ids=tuple(str(item) for item in constraint_ids),
                parent_goal_id=body.get("parent_goal_id"),
                priority=50 if body.get("priority") is None else body.get("priority"),
                occurred_at_ms=int(time.time() * 1000),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        return {"tenant_id": tenant_id, "business_id": business_id, "goal": goal}

    @router.get("/business-workspace/discovery/constraints", tags=["business-workspace"])
    async def discovery_constraints(request: Request) -> dict[str, Any]:
        _, tenant_id, business_id = business_owner_scope(
            request=request,
            auth_bundle=auth_bundle,
            required_scope="provider_control_plane",
        )
        return {
            "tenant_id": tenant_id,
            "business_id": business_id,
            "constraints": workspace.list_constraints(
                tenant_id=tenant_id,
                business_id=business_id,
            ),
        }

    @router.post("/business-workspace/discovery/constraints", tags=["business-workspace"])
    async def create_discovery_constraint(request: Request) -> dict[str, Any]:
        principal, tenant_id, business_id = business_owner_scope(
            request=request,
            auth_bundle=auth_bundle,
            required_scope="provider_control_plane",
        )
        body = await json_body(request)
        extra = set(body).difference(_ALLOWED_CONSTRAINT_KEYS)
        if extra:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="business_discovery_unknown_constraint_fields",
            )
        key = _idempotency_key(request)
        if not key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="idempotency_key_required",
            )
        confirmed = body.get("confirmed")
        if not isinstance(confirmed, bool):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="confirmed_must_be_boolean",
            )
        try:
            constraint = workspace.create_constraint(
                tenant_id=tenant_id,
                business_id=business_id,
                actor_id=_actor_id(principal),
                idempotency_key=key,
                confirmed=confirmed,
                constraint_id=str(body.get("constraint_id") or ""),
                constraint_kind=str(body.get("constraint_kind") or ""),
                severity=str(body.get("severity") or "hard"),
                subject_type=body.get("subject_type"),
                subject_id=body.get("subject_id"),
                state_key=body.get("state_key"),
                comparison=body.get("comparison"),
                threshold=body.get("threshold"),
                occurred_at_ms=int(time.time() * 1000),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        return {
            "tenant_id": tenant_id,
            "business_id": business_id,
            "constraint": constraint,
        }

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
