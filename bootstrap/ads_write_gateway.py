from __future__ import annotations
CANON_BOOT_ADS_WRITE_GATEWAY_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True


from dataclasses import dataclass
from typing import Any, Dict

from runtime.ads import BudgetGuardrails, CircuitBreaker, EventLogSink
from interfaces.ads.base import AdsConnector
from interfaces.ads.registry import AdsConnectorRegistry
from runtime.observability.error_handling import swallow


Json = Dict[str, Any]


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

        c: AdsConnector | None = self._registry.get(req.platform)
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

        out: Json = {"status": "ok", "applied": len(results), "results": results}
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