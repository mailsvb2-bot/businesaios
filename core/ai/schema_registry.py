from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.service_names import RuntimeServiceName


@dataclass(frozen=True)
class DecisionSchema:
    required: set[str]
    optional: set[str]
    field_types: dict[str, type[Any] | tuple[type[Any], ...]]

    def validate(self, payload: dict):
        if payload is None:
            raise ValueError("PAYLOAD_MISSING")
        if not isinstance(payload, dict):
            raise ValueError("PAYLOAD_NOT_OBJECT")

        keys = set(payload.keys())
        if not self.required.issubset(keys):
            raise ValueError("MISSING_REQUIRED_KEYS")
        reserved_optional = {
            "idempotency_key",
            "meta",
            "world_model_meta",
            "tenant_id",
            "business_id",
            "user_id",
            "autonomy_tier",
            "approval_policy",
            "constraints",
            "economy",
            "goal_plan",
            "previous_feedback",
            "capability_planning",
            "routing_explanation",
            "autonomy_safety",
            "autonomy_policy_snapshot",
            "autonomy_audit",
            "blast_radius_guard",
            "bounded_autonomy",
            "execution_verdict",
            "policy_verdict",
            "capability_diagnostics",
            RuntimeServiceName.ACTION_BUDGET,
        }
        if not keys.issubset(self.required | self.optional | reserved_optional):
            raise ValueError("UNKNOWN_PAYLOAD_KEYS")

        # Type validation
        for k, t in self.field_types.items():
            if k not in payload:
                continue
            v = payload[k]
            if not isinstance(v, t):
                raise ValueError("BAD_PAYLOAD_TYPE")


class SchemaRegistry:
    """Action->(version,schema) registry.

    Invariants:
    - Unknown actions are forbidden.
    - Extra keys are forbidden.
    - Versioned schemas are mandatory.

    NOTE: registry is injectable; do not use a global singleton.
    """

    def __init__(self):
        self._schemas: dict[str, dict[int, DecisionSchema]] = {}

    def register(self, action: str, version: int, schema: DecisionSchema) -> None:
        action = str(action)
        version = int(version)
        versions = self._schemas.setdefault(action, {})
        if version in versions:
            # Disallow silent schema drift (governance requirement).
            # Allow re-register only if bit-identical.
            if versions[version] != schema:
                raise RuntimeError("SCHEMA_VERSION_ALREADY_REGISTERED")
            return
        versions[version] = schema

    def validate(self, action: str, payload: dict, *, version: int | None = None) -> int:
        action = str(action)
        if action not in self._schemas:
            raise ValueError("UNKNOWN_ACTION")

        versions = self._schemas[action]
        if version is None:
            # default to max version
            version = max(versions.keys())
        version = int(version)

        if version not in versions:
            raise ValueError("UNKNOWN_ACTION_VERSION")
        versions[version].validate(payload)
        return version

    def latest_version(self, action: str) -> int:
        action = str(action)
        if action not in self._schemas:
            raise ValueError("UNKNOWN_ACTION")
        return max(self._schemas[action].keys())
