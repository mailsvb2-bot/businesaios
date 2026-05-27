from __future__ import annotations

from typing import Any, Mapping

from core.behavior.operator_catalogs.models import OperatorCatalog, catalog_from_raw


def parse_operator_catalog(data: Mapping[str, Any]) -> OperatorCatalog:
    """Parse operator catalog from YAML/JSON payload.

    Canonical model accepts bounded scalar maps only. Legacy payloads that
    accidentally contain tuple/list values are safely ignored instead of
    creating a divergent catalog shape.
    """
    payload = dict(data or {})
    for key in ("event_scales", "domain_scales", "channel_scales"):
        raw = payload.get(key, {}) or {}
        if not isinstance(raw, dict):
            payload[key] = {}
            continue
        payload[key] = {
            str(k): float(v)
            for k, v in raw.items()
            if isinstance(v, (int, float))
        }
    return catalog_from_raw(payload)
