"""Purpose-scoped pseudonym tokens and bounded lineage exports, no global lookup."""
from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping


def purpose_token(
    value: str, *, key: bytes, key_id: str, tenant: str, business: str, controller: str, purpose: str
) -> str:
    if len(key) < 32 or not all((value, key_id, tenant, business, controller, purpose)):
        raise ValueError("complete scope and >=256-bit key required")
    message = json.dumps(
        ["uiii-token-v1", tenant, business, controller, purpose, value],
        ensure_ascii=False, separators=(",", ":"),
    ).encode()
    return key_id + ":" + hmac.new(key, message, hashlib.sha256).hexdigest()


def lineage_event(*, run_id: str, job: str, namespace: str, at: str, datasets: list[Mapping[str, str]]) -> dict:
    """OpenLineage-shaped metadata; not an actual export transport or full PROV graph."""
    from datetime import datetime
    from uuid import UUID

    UUID(run_id)
    if datetime.fromisoformat(at.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("timezone required")
    if not job or not namespace or len(datasets) > 100:
        raise ValueError("bounded lineage context required")
    inputs = []
    for item in datasets:
        if set(item) != {"namespace", "name"} or not all(
            isinstance(v, str) and v and len(v) < 200 for v in item.values()
        ):
            raise ValueError("opaque dataset reference required")
        inputs.append(dict(item))
    return {
        "eventType": "COMPLETE",
        "eventTime": at,
        "run": {"runId": run_id},
        "job": {"namespace": namespace, "name": job},
        "inputs": inputs,
        "outputs": [],
        "producer": "urn:uiii:lineage:1",
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
    }
