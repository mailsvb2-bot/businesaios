"""Action schema catalog bound to the canonical runtime action registry.

Runtime Action Registry owns executable action names. This module owns payload
schema details only; it cannot advertise a second set of actions.
"""

from __future__ import annotations

from core.actions.allowed_actions import ALLOWED_ACTIONS
from core.ai.schema_registry import DecisionSchema, SchemaRegistry

from .catalog_entry import CatalogEntry
from .catalog_groups import build_catalog_groups


def _marker_event_entry(action: str) -> CatalogEntry:
    return CatalogEntry(
        action=action,
        version=1,
        schema=DecisionSchema(
            required=set(),
            optional={
                "tenant_id",
                "product_id",
                "user_id",
                "event_type",
                "payload",
                "source",
            },
            field_types={
                "tenant_id": str,
                "product_id": str,
                "user_id": str,
                "event_type": str,
                "payload": dict,
                "source": str,
            },
        ),
    )


def _runtime_contract_entries() -> dict[str, CatalogEntry]:
    """Explicit contracts for advisory and marker actions.

    These actions historically fell through to a permissive compatibility
    schema. Keeping their exact payload surfaces here preserves behavior while
    ensuring that every executable action is closed and versioned.
    """

    return {
        "ads_rl_report@v1": CatalogEntry(
            action="ads_rl_report@v1",
            version=1,
            schema=DecisionSchema(
                required={"tenant_id"},
                optional=set(),
                field_types={"tenant_id": str},
            ),
        ),
        "autopilot_decision@v1": _marker_event_entry(
            "autopilot_decision@v1"
        ),
        "autopilot_run_started@v1": _marker_event_entry(
            "autopilot_run_started@v1"
        ),
        "autopilot_started@v1": _marker_event_entry(
            "autopilot_started@v1"
        ),
        "telegram_self_check@v1": CatalogEntry(
            action="telegram_self_check@v1",
            version=1,
            schema=DecisionSchema(
                required=set(),
                optional={"token"},
                field_types={"token": str},
            ),
        ),
    }


def build_catalog() -> dict[str, CatalogEntry]:
    declared: dict[str, CatalogEntry] = {}
    groups = (*build_catalog_groups(), _runtime_contract_entries())
    for group in groups:
        overlap = set(declared) & set(group)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"duplicate catalog actions: {names}")
        declared.update(group)

    active_actions = {str(action) for action in ALLOWED_ACTIONS}
    missing = active_actions - set(declared)
    retired = set(declared) - active_actions
    if missing or retired:
        missing_names = ", ".join(sorted(missing)) or "-"
        retired_names = ", ".join(sorted(retired)) or "-"
        raise RuntimeError(
            "ACTION_SCHEMA_CATALOG_DRIFT: "
            f"missing=[{missing_names}] retired=[{retired_names}]"
        )

    return {action: declared[action] for action in sorted(active_actions)}


def build_schema_registry() -> SchemaRegistry:
    reg = SchemaRegistry()
    for entry in build_catalog().values():
        reg.register(entry.action, entry.version, entry.schema)
    return reg
