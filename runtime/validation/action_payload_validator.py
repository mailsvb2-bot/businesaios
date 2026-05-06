from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from runtime.enforcement import ActionSchemaRegistry


@dataclass(frozen=True)
class PayloadValidationError(Exception):
    action: str
    reason: str

    def __str__(self) -> str:
        return f"PayloadValidationError(action={self.action!r}, reason={self.reason!r})"


def _is_type(v: Any, t: str) -> bool:
    if t == "object":
        return isinstance(v, dict)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float))
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    return True  # unknown -> do not block


def validate_action_payload(registry: ActionSchemaRegistry, action: str, payload: Mapping[str, Any]) -> None:
    spec = registry.get(action)
    if spec is None:
        # Registry missing schema should be caught by locks; runtime stays permissive here.
        return
    schema = spec.schema
    if schema.get("type") == "object" and not isinstance(payload, dict):
        raise PayloadValidationError(action, "payload must be an object/dict")

    required = schema.get("required", [])
    for k in required:
        if k not in payload:
            raise PayloadValidationError(action, f"missing required field: {k}")

    props = schema.get("properties", {})
    for k, ks in props.items():
        if k in payload and isinstance(ks, dict) and "type" in ks:
            if not _is_type(payload[k], ks["type"]):
                raise PayloadValidationError(action, f"field {k} must be {ks['type']}")
