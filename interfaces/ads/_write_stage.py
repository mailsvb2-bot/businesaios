from __future__ import annotations

from typing import Any, Dict

from .base import AdsConnectorError


def raise_write_stage_disabled(*, connector_name: str, provider: str, operation: str, payload: dict[str, Any] | None = None) -> None:
    payload_keys = sorted(str(k) for k in (payload or {}).keys())
    raise AdsConnectorError(
        f"{connector_name}: write surface is disabled (provider={provider}, operation={operation}, stage=read_only, payload_keys={payload_keys}, hint=wire explicit provider-specific writer before enabling apply)"
    )
