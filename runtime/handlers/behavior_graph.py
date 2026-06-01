from __future__ import annotations

CANON_THIN_HANDLER = True


import logging
import time
from typing import Any, Dict

from contracts.behavior_graph import GraphSnapshot
from runtime.behavior import BehaviorGraphStore, build_behavior_graph_from_events
from runtime.tenancy import require_tenant_id

logger = logging.getLogger(__name__)

def _scope_from_payload(p: dict) -> str:
    scope = str(p.get("scope") or "").strip()
    if scope:
        return scope
    # fallback: if user_id provided => per-user scope
    uid = str(p.get("user_id") or "").strip()
    if uid:
        return f"user:{uid}"
    return "tenant"


def handle_behavior_graph_build(
    payload: dict[str, Any] | None,
    effects: Any,
    env: Any,
    *,
    event_store: Any,
    store: BehaviorGraphStore,
) -> dict[str, Any]:
    p = dict(payload or {})
    tenant_id = require_tenant_id(p.get("tenant_id") or getattr(getattr(env, "tenant", None), "tenant_id", None) or "")
    scope = _scope_from_payload(p)
    user_id = str(p.get("user_id") or "").strip()
    start_ms = int(p.get("start_ms") or 0)
    end_ms = p.get("end_ms")
    end_ms_int = int(end_ms) if end_ms is not None else None
    max_events = int(p.get("max_events") or 5000)
    enable_sequence_edges = bool(p.get("enable_sequence_edges", True))

    # Pull events (bounded; best-effort).
    events_iter = event_store.iter_events(tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=end_ms_int,
        user_id=(user_id if user_id else None),
        event_type=None,
    )
    events = list(events_iter)
    nodes, edges, meta = build_behavior_graph_from_events(
        events=events,
        max_events=max_events,
        enable_sequence_edges=enable_sequence_edges,
    )
    built_at_ms = int(time.time() * 1000)

    store.upsert_snapshot(
        tenant_id=tenant_id,
        scope=scope,
        built_at_ms=built_at_ms,
        nodes=nodes,
        edges=edges,
        meta={
            **(meta or {}),
            "tenant_id": tenant_id,
            "scope": scope,
            "source_events": len(events),
            "user_id": (user_id or None),
        },
    )

    # Emit telemetry (optional)
    try:
        effects.track_event(
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            user_id=(user_id or "system"),
            event_type="behavior_graph_built",
            payload={"tenant_id": tenant_id, "scope": scope, **(meta or {})},
            source="behavior_graph",
        )
    except Exception as exc:
        logger.warning("telemetry emission failed", extra={"component": __name__, "error": str(exc)})

    return {
        "ok": True,
        "tenant_id": tenant_id,
        "scope": scope,
        "built_at_ms": built_at_ms,
        "meta": meta,
    }


def handle_behavior_graph_node(
    payload: dict[str, Any] | None,
    effects: Any,
    env: Any,
    *,
    store: BehaviorGraphStore,
) -> dict[str, Any]:
    p = dict(payload or {})
    tenant_id = require_tenant_id(p.get("tenant_id") or getattr(getattr(env, "tenant", None), "tenant_id", None) or "")
    scope = _scope_from_payload(p)
    node_id = str(p.get("node_id") or "").strip()
    if not node_id:
        return {"ok": False, "error": "MISSING_NODE_ID"}
    n = store.get_node(tenant_id=tenant_id, scope=scope, node_id=node_id)
    if n is None:
        return {"ok": False, "error": "NOT_FOUND", "node_id": node_id}
    return {"ok": True, "node": {"node_id": n.node_id, "node_type": n.node_type, "key": n.key, "title": n.title, "props": n.props}}


def handle_behavior_graph_neighbors(
    payload: dict[str, Any] | None,
    effects: Any,
    env: Any,
    *,
    store: BehaviorGraphStore,
) -> dict[str, Any]:
    p = dict(payload or {})
    tenant_id = require_tenant_id(p.get("tenant_id") or getattr(getattr(env, "tenant", None), "tenant_id", None) or "")
    scope = _scope_from_payload(p)
    node_id = str(p.get("node_id") or "").strip()
    if not node_id:
        return {"ok": False, "error": "MISSING_NODE_ID"}
    direction = str(p.get("direction") or "out").strip().lower()
    limit = int(p.get("limit") or 50)
    edge_type = str(p.get("edge_type") or "").strip() or None
    neigh = store.neighbors(
        tenant_id=tenant_id,
        scope=scope,
        node_id=node_id,
        direction=direction,
        limit=limit,
        edge_type=edge_type,
    )
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "scope": scope,
        "node_id": node_id,
        "neighbors": [
            {"node_id": n.node_id, "weight": n.weight, "edge_type": n.edge_type, "edge_id": n.edge_id, "props": n.props}
            for n in neigh
        ],
    }


def handle_behavior_graph_path(
    payload: dict[str, Any] | None,
    effects: Any,
    env: Any,
    *,
    store: BehaviorGraphStore,
) -> dict[str, Any]:
    p = dict(payload or {})
    tenant_id = require_tenant_id(p.get("tenant_id") or getattr(getattr(env, "tenant", None), "tenant_id", None) or "")
    scope = _scope_from_payload(p)
    src = str(p.get("src") or "").strip()
    dst = str(p.get("dst") or "").strip()
    if not src or not dst:
        return {"ok": False, "error": "MISSING_SRC_DST"}
    max_hops = int(p.get("max_hops") or 6)
    steps = store.shortest_path(tenant_id=tenant_id, scope=scope, src=src, dst=dst, max_hops=max_hops)
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "scope": scope,
        "src": src,
        "dst": dst,
        "path": [
            {"node_id": s.node_id, "via_edge_id": s.via_edge_id, "via_edge_type": s.via_edge_type, "weight": s.weight}
            for s in steps
        ],
    }


def handle_behavior_graph_reset(
    payload: dict[str, Any] | None,
    effects: Any,
    env: Any,
    *,
    store: BehaviorGraphStore,
) -> dict[str, Any]:
    p = dict(payload or {})
    tenant_id = require_tenant_id(p.get("tenant_id") or getattr(getattr(env, "tenant", None), "tenant_id", None) or "")
    scope = _scope_from_payload(p)
    store.reset(tenant_id=tenant_id, scope=scope)
    return {"ok": True, "tenant_id": tenant_id, "scope": scope}
