from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_ADS_APPLY_PROVIDER_FINAL_OWNER = True

from typing import Any, Dict

from runtime.ads import AdsPlan
from shared.asyncio_bridge import run_awaitable_sync
from bootstrap.ads_write_gateway import AdsWriteGateway, AdsWriteRequest


def _run(coro):
    """Run an async coroutine from sync context through the canonical bridge."""

    return run_awaitable_sync(coro, thread_name_prefix="ads-apply-sync")


class AdsGatewayApplyPort:
    """Runtime apply port for core.ads.apply_engine.

    Converts AdsPlan (list of commands) to AdsWriteGateway.apply_plan calls.
    """

    def __init__(self, gateway: AdsWriteGateway) -> None:
        self._gw = gateway

    def perform_apply(self, tenant_id: str, plan: AdsPlan) -> Dict[str, Any]:
        out: Dict[str, Any] = {"status": "ok", "items": []}
        for cmd in (plan.commands or []):
            req = AdsWriteRequest(
                tenant_id=str(tenant_id),
                platform=str(cmd.platform),
                plan=dict(cmd.payload or {}),
                correlation_key="ads_apply_engine",
            )
            res = _run(self._gw.apply_plan(req))
            out["items"].append({"platform": str(cmd.platform), "result": res})
        return out
