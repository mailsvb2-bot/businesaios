from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.actions.names import ACTION_GROWTH_PROPOSE_V1

CANON_GROWTH_COMPAT_FORWARDER = True


class GrowthProposalService:
    """Compatibility forwarder to the one canonical Growth Strategy owner.

    This legacy surface performs no scoring, thresholding or proposal ranking.
    It only preserves older callers by carrying their inputs into the registered
    ``growth_propose@v1`` action. Decision signing and execution remain owned by
    the canonical gateway and Growth Strategy service.
    """

    def build_proposals(
        self,
        *,
        tenant_id: str,
        objective: str,
        signals: dict[str, Any],
        user_id: str = "",
    ) -> list[dict[str, Any]]:
        tenant = str(tenant_id or "").strip()
        if not tenant:
            raise RuntimeError("TENANT_ID_REQUIRED")
        return [
            {
                "tenant_id": tenant,
                "user_id": str(user_id or "").strip(),
                "objective": str(objective or "").strip(),
                "signals": dict(signals or {}),
            }
        ]

    def queue(
        self,
        *,
        gateway: Any,
        tenant_id: str,
        decision_id: str,
        correlation_id: str,
        issuer_id: str,
        proposals: Iterable[dict[str, Any]],
        user_id: str = "",
    ) -> int:
        tenant = str(tenant_id or "").strip()
        if not tenant:
            raise RuntimeError("TENANT_ID_REQUIRED")
        for field, value in (
            ("decision_id", decision_id),
            ("correlation_id", correlation_id),
            ("issuer_id", issuer_id),
        ):
            if not str(value or "").strip():
                raise RuntimeError(f"{field.upper()}_REQUIRED")

        queued = 0
        for proposal in proposals:
            if not isinstance(proposal, Mapping):
                raise RuntimeError("GROWTH_REQUEST_MAPPING_REQUIRED")
            request = dict(proposal)
            request_tenant = str(request.get("tenant_id") or tenant).strip()
            if request_tenant != tenant:
                raise RuntimeError("TENANT_CONTEXT_MISMATCH:growth_proposal")
            request_user = str(user_id or request.get("user_id") or "").strip()
            if not request_user:
                raise RuntimeError("USER_ID_REQUIRED")
            payload = {
                "tenant_id": tenant,
                "user_id": request_user,
                "objective": str(request.get("objective") or "").strip(),
                "signals": (
                    dict(request.get("signals") or {})
                    if isinstance(request.get("signals"), Mapping)
                    else {}
                ),
            }
            gateway.propose(
                tenant_id=tenant,
                action=ACTION_GROWTH_PROPOSE_V1,
                payload=payload,
            )
            queued += 1
        return queued
