"""POST /businesaios/webhooks/xp/{connector_id}: signed external-product events -> injected ingest."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


def register_external_product_webhook_routes(*, router, ingest: Callable[..., tuple[int, str]]) -> None:
    @router.post("/businesaios/webhooks/xp/{connector_id}", response_model=None)
    async def external_product_webhook(connector_id: str, request: Request):
        raw = await request.body()
        status, code = ingest(connector_id=connector_id, raw_body=raw,
                              headers={str(k): str(v) for k, v in request.headers.items()})  # fmt: skip
        if status >= 400:
            raise HTTPException(status_code=status, detail="external_product_webhook_rejected")
        return JSONResponse({"status": code}, status_code=status)


__all__ = ["register_external_product_webhook_routes"]
