from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.actions.action_names import ADS_APPLY_EXECUTE_V1

JsonSchema = Dict[str, Any]


@dataclass(frozen=True)
class ActionSchemaSpec:
    name: str
    schema: JsonSchema


class ActionSchemaRegistry:
    def __init__(self, specs: list[ActionSchemaSpec]) -> None:
        self._by_name: dict[str, ActionSchemaSpec] = {s.name: s for s in specs}

    def names(self) -> set[str]:
        return set(self._by_name.keys())

    def get(self, action_name: str) -> ActionSchemaSpec | None:
        return self._by_name.get(action_name)

    def register(self, name: str, schema: JsonSchema) -> None:
        self._by_name[str(name)] = ActionSchemaSpec(name=str(name), schema=dict(schema))


def _base_specs() -> list[ActionSchemaSpec]:
    return [
        ActionSchemaSpec(
            name=ADS_APPLY_EXECUTE_V1,
            schema={
                "type": "object",
                "required": ["plan_id", "dry_run", "idempotency_key"],
                "properties": {
                    "plan_id": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                    "idempotency_key": {"type": "string"},
                },
                "additionalProperties": True,
            },
        ),
    ]


def build_default_registry() -> ActionSchemaRegistry:
    reg = ActionSchemaRegistry(_base_specs())
    try:
        from runtime.boot.actions_registry import all_actions
        for name in sorted(all_actions()):
            if name not in reg.names():
                reg.register(name, {"type": "object", "additionalProperties": True})
    except Exception as exc:
        if event_log is not None and hasattr(event_log, "emit"):
            event_log.emit(event_type="schema_registry_missing@v1", source="schema_registry", user_id="-", decision_id="-", correlation_id="-", payload={"action": str(action), "error": exc.__class__.__name__})
        raise RuntimeError(f"SCHEMA_REGISTRY_LOOKUP_FAILED:{exc.__class__.__name__}") from exc
    return reg
