"""UCR gateway transport inside the sealed effects perimeter.

Reuses runtime._internal.http_transport.sync_request (no new network primitive importer).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

from interfaces.ucr.gateway import UcrGatewayProtocolError, UcrGatewayUnavailable
from runtime._internal.http_transport import sync_request


class SyncRequestUcrGatewayTransport:
    """Bounded UCR transport: finite timeout, declared and actual response size limits."""

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> tuple[int, Mapping[str, str], bytes]:
        body = None if payload is None else json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
        hdrs = dict(headers)
        if body is not None:
            hdrs.setdefault("Content-Type", "application/json")
        result = await asyncio.to_thread(
            sync_request, method=method, url=url, headers=hdrs, body=body, timeout_s=float(timeout_seconds)
        )
        if result.status is None:
            raise UcrGatewayUnavailable("UCR gateway request failed")
        declared = {k.lower(): v for k, v in result.headers.items()}.get("content-length")
        if declared:
            try:
                declared_bytes = int(declared)
            except ValueError as exc:
                raise UcrGatewayProtocolError("UCR gateway returned an invalid content length") from exc
            if declared_bytes < 0 or declared_bytes > max_response_bytes:
                raise UcrGatewayProtocolError("UCR gateway response exceeded the configured limit")
        raw = result.text.encode("utf-8") if result.json is None else json.dumps(result.json).encode("utf-8")
        if len(raw) > max_response_bytes:
            raise UcrGatewayProtocolError("UCR gateway response exceeded the configured limit")
        return int(result.status), dict(result.headers), raw


__all__ = ["SyncRequestUcrGatewayTransport"]
