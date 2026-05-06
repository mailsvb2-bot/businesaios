from __future__ import annotations

from importlib import import_module
from typing import Any

CANON_CONNECTOR_REGISTRY_MATRIX = True

_REGISTRY_MODULES: tuple[tuple[str, str], ...] = (
    ("ads", "interfaces.ads.registry"),
    ("crm", "interfaces.crm.registry"),
    ("platforms", "interfaces.platforms.registry"),
    ("reviews", "interfaces.reviews.registry"),
    ("website", "interfaces.website.registry"),
    ("communications", "interfaces.communications.registry"),
    ("market_intelligence", "interfaces.market_intelligence.registry"),
)


def _registry_items() -> list[tuple[str, str, dict[str, Any]]]:
    items: list[tuple[str, str, dict[str, Any]]] = []
    for domain, module_name in _REGISTRY_MODULES:
        module = import_module(module_name)
        connectors = getattr(module, "CONNECTORS", {}) or {}
        for name, entry in connectors.items():
            if isinstance(entry, dict):
                items.append((domain, str(name), dict(entry)))
    items.sort(key=lambda item: (item[0], item[1]))
    return items


def build_connector_registry_matrix_payload() -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for domain, connector_name, entry in _registry_items():
        truth = dict(entry.get("truth_layer") or {})
        truth.setdefault("implemented", bool(entry.get("implemented") or entry.get("status") == "implemented"))
        truth.setdefault("stub", bool(entry.get("stub", entry.get("status") != "implemented")))
        truth.setdefault("write_enabled", bool(entry.get("write")))
        truth.setdefault("verify_enabled", bool(entry.get("verify")))
        truth.setdefault("dry_run_enabled", bool(entry.get("supports_dry_run")))
        truth.setdefault("idempotent", bool(entry.get("supports_idempotency")))
        truth.setdefault("reversible", bool(entry.get("reversible")))
        truth.setdefault("requires_human_approval", bool(entry.get("requires_human_approval", True)))
        payload.append(
            {
                "domain": domain,
                "connector_name": connector_name,
                "status": str(entry.get("status") or ""),
                "implemented": bool(entry.get("implemented") or entry.get("status") == "implemented"),
                "stub": bool(entry.get("stub", entry.get("status") != "implemented")),
                "production_ready": bool(entry.get("production_ready")),
                "read": bool(entry.get("read")),
                "write": bool(entry.get("write")),
                "verify": bool(entry.get("verify")),
                "supports_dry_run": bool(entry.get("supports_dry_run")),
                "supports_idempotency": bool(entry.get("supports_idempotency")),
                "reversible": bool(entry.get("reversible")),
                "requires_human_approval": bool(entry.get("requires_human_approval", True)),
                "action_types": list(entry.get("action_types") or []),
                "truth_layer": truth,
            }
        )
    return payload


__all__ = ["CANON_CONNECTOR_REGISTRY_MATRIX", "build_connector_registry_matrix_payload"]
