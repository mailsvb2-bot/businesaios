from __future__ import annotations

from typing import Any

from runtime.handler_impl.core.payloads import optional_str, require_mapping, required_str
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True


def _ids(body: dict[str, Any], env: Any) -> dict[str, str]:
    return {"decision_id": str(env.decision.decision_id), "correlation_id": str(env.decision.correlation_id), "tenant_id": required_str(body, "tenant_id"), "user_id": required_str(body, "user_id")}


def handle_generate_visual_creative(payload: dict[str, Any], effects: EffectsPort, env: Any) -> Any:
    body = require_mapping(payload)
    return effects.generate_visual_creative(**_ids(body, env), kind=required_str(body, "kind"), prompt=required_str(body, "prompt"), country_code=optional_str(body, "country_code") or "", preferred_provider=optional_str(body, "preferred_provider") or "", aspect_ratio=optional_str(body, "aspect_ratio") or "1:1", duration_seconds=int(body.get("duration_seconds") or 5), negative_prompt=optional_str(body, "negative_prompt") or "", reference_url=optional_str(body, "reference_url") or "", brand_context=optional_str(body, "brand_context") or "", wait_seconds=int(body.get("wait_seconds") or 0))


def handle_poll_visual_creative(payload: dict[str, Any], effects: EffectsPort, env: Any) -> Any:
    body = require_mapping(payload)
    return effects.poll_visual_creative(**_ids(body, env), job_id=required_str(body, "job_id"))


__all__ = ["handle_generate_visual_creative", "handle_poll_visual_creative"]
