from __future__ import annotations

from dataclasses import dataclass
from inspect import isawaitable
from typing import Any

from interfaces.ads.base import AdsConnector
from interfaces.ads.registry import AdsConnectorRegistry
from runtime.ads import BudgetGuardrails, CircuitBreaker, EventLogSink
from runtime.observability.error_handling import swallow

CANON_BOOT_ADS_WRITE_GATEWAY_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True

Json = dict[str, Any]


@dataclass(frozen=True)
class AdsWriteRequest:
    tenant_id: str
    platform: str
    plan: Json
    correlation_key: str = ""


class AdsWriteGateway:
    """Guarded writes facade over Ads connectors.

    Lives in runtime/boot to keep layer direction strict:
      core -> (no provider imports)
      runtime -> wiring + guarded IO
      platform_layer/interfaces -> connectors
    """

    def __init__(
        self,
        *,
        registry: AdsConnectorRegistry,
        guardrails: BudgetGuardrails,
        circuit_breaker: CircuitBreaker,
        sink: EventLogSink,
        writes_enabled: bool,
    ) -> None:
        self._registry = registry
        self._guard = guardrails
        self._cb = circuit_breaker
        self._sink = sink
        self._writes_enabled = bool(writes_enabled)

    async def apply_plan(self, req: AdsWriteRequest) -> Json:
        if not self._writes_enabled:
            return {"status": "skipped", "reason": "writes_disabled"}

        if not self._cb.allow(key=f"ads:{req.tenant_id}:{req.platform}"):
            return {"status": "skipped", "reason": "circuit_breaker"}

        if not self._guard.allow_apply(platform=req.platform, plan=req.plan):
            return {"status": "skipped", "reason": "guardrails"}

        c: AdsConnector | None = self._registry.get_optional(req.platform)
        if c is None:
            return {"status": "skipped", "reason": "connector_not_configured", "platform": req.platform}

        # Contract alignment:
        # Interfaces AdsConnector exposes async write primitive: create_or_update(...)
        # Gateway applies a "plan" by executing a sequence of create_or_update operations.
        ops = list((req.plan or {}).get("ops") or [])
        if not ops:
            return {"status": "skipped", "reason": "empty_plan"}

        results = []
        for op in ops:
            try:
                account_id = str(op.get("account_id") or "").strip()
                object_type = str(op.get("object_type") or "").strip()
                payload = dict(op.get("payload") or {})
                if not account_id or not object_type:
                    results.append({"status": "skipped", "reason": "invalid_op", "op": op})
                    continue
                results.append(
                    await c.create_or_update(
                        tenant_id=req.tenant_id,
                        account_id=account_id,
                        object_type=object_type,
                        payload=payload,
                    )
                )
            except Exception:
                swallow(__name__, "ads_write_gateway.apply_plan")
                results.append({"status": "error", "reason": "connector_error"})

        out: Json = {"status": "ok" if all(isinstance(row, dict) and row.get("status") not in {"error", "skipped", "failed"} for row in results) else "blocked", "applied": len(results), "results": results}
        try:
            self._sink.emit(
                tenant_id=req.tenant_id,
                event_type="ads_plan_applied",
                payload={
                    "platform": req.platform,
                    "correlation_key": req.correlation_key,
                    "plan": req.plan,
                    "result": out,
                },
            )
        except Exception:
            swallow(__name__, "ads_write_gateway.emit")
        return out

@dataclass(frozen=True)
class ReviewedAdPublication:
    """A single media-bearing write request, not a permission grant."""

    tenant_id: str
    business_id: str
    publication_job_id: str
    platform: str
    account_id: str
    object_type: str
    payload: Json
    asset: Any
    approval_reference: str
    execution_reference: str


async def submit_reviewed_ad_publication(
    *, gateway: AdsWriteGateway, request: ReviewedAdPublication,
    verify_approval: Any, reserve_execution: Any, verify_provider: Any,
) -> Json:
    """Canonical guarded one-shot publish with authoritative provider read-back.

    All three injected authorities must come from server-owned durable owners.
    Missing proof fails closed. An ambiguous provider result must be reconciled
    under the original reservation, never retried with a new write.
    """
    from contracts.ad_publication_asset import require_scoped_asset_review
    from interfaces.ads.registry import CONNECTORS

    def blocked(reason: str) -> Json:
        return {"status": "blocked", "reason": reason,
                "publication_job_id": request.publication_job_id}

    if not request.tenant_id or not request.business_id or not request.publication_job_id:
        return blocked("scope_missing")
    if not request.account_id or not request.approval_reference or not request.execution_reference:
        return blocked("publication_binding_missing")
    if request.platform not in CONNECTORS:
        return blocked("unknown_ads_provider")
    provider = CONNECTORS[request.platform]
    if not (provider["implemented"] and provider["write"] and provider["verify"]
            and provider["production_ready"]):
        return blocked("provider_write_and_verification_unavailable")
    try:
        require_scoped_asset_review(
            request.asset, tenant_id=request.tenant_id,
            business_id=request.business_id,
            publication_job_id=request.publication_job_id,
        )
    except (TypeError, ValueError, PermissionError, RuntimeError):
        return blocked("asset_not_eligible")
    if not all(callable(x) for x in (verify_approval, reserve_execution, verify_provider)):
        return blocked("canonical_authorities_missing")
    proof = verify_approval(
        tenant_id=request.tenant_id, business_id=request.business_id,
        publication_job_id=request.publication_job_id,
        approval_reference=request.approval_reference,
        payload=request.payload, asset=request.asset,
    )
    if proof is not True:
        return blocked("owner_approval_not_verified")
    reservation = reserve_execution(
        tenant_id=request.tenant_id, business_id=request.business_id,
        publication_job_id=request.publication_job_id,
        execution_reference=request.execution_reference,
    )
    if reservation != "claimed":
        return blocked("publication_execution_already_reserved")
    # A subsequent exception or network ambiguity preserves the durable
    # reservation, preventing duplicate advertisements and spending.
    try:
        result = await gateway.apply_plan(AdsWriteRequest(
            tenant_id=request.tenant_id,
            platform=request.platform,
            correlation_key=request.execution_reference,
            plan={"ops": [{
                "account_id": request.account_id,
                "object_type": request.object_type,
                "payload": request.payload,
            }]},
        ))
        if result.get("status") != "ok" or len(result.get("results") or ()) != 1:
            return blocked("canonical_ads_gateway_declined")
        receipt = result["results"][0]
        if not isinstance(receipt, dict) or not receipt.get("object_id"):
            return blocked("provider_acceptance_ambiguous")
        evidence = verify_provider(
            tenant_id=request.tenant_id, business_id=request.business_id,
            platform=request.platform, account_id=request.account_id,
            publication_job_id=request.publication_job_id,
            object_id=receipt["object_id"],
            asset=request.asset,
        )
        if isawaitable(evidence):
            evidence = await evidence
        if not isinstance(evidence, dict) or evidence.get("verified") is not True:
            return blocked("provider_publication_unconfirmed")
        if evidence.get("object_id") != receipt["object_id"]:
            return blocked("provider_identity_mismatch")
        return {
            "status": "verified", "publication_job_id": request.publication_job_id,
            "provider_object_id": receipt["object_id"],
            "execution_reference": request.execution_reference,
        }
    except Exception:
        return blocked("publication_outcome_ambiguous")
