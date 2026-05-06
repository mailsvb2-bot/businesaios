from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple

from contracts.behavior_graph import Edge, EdgeType, Node, NodeType
from core.behavior_graph.event_mapping import map_events
from core.behavior_graph.ids import canonical_edge_id, canonical_node_id


def _node(*, node_type: str, key: str, title: str, props: Dict[str, Any]) -> Node:
    nid = canonical_node_id(node_type=node_type, key=key)
    return Node(node_id=nid, node_type=str(node_type), key=str(key), title=str(title), props=dict(props or {}))


def _edge(*, edge_type: str, src: str, dst: str, weight: float, props: Dict[str, Any], salt: str = "") -> Edge:
    eid = canonical_edge_id(edge_type=edge_type, src=src, dst=dst, salt=salt)
    return Edge(edge_id=eid, edge_type=str(edge_type), src=str(src), dst=str(dst), weight=float(weight), props=dict(props or {}))


def build_behavior_graph_from_events(
    *,
    events: Iterable[Dict[str, Any]],
    max_events: int = 5000,
    enable_sequence_edges: bool = True,
) -> tuple[list[Node], list[Edge], dict]:
    """Build a bounded behavior graph from event dictionaries."""

    mapped = map_events(events)
    if max_events and len(mapped) > int(max_events):
        mapped = mapped[-int(max_events) :]

    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}

    def upsert_node(n: Node) -> None:
        nodes[n.node_id] = n

    def bump_edge(e: Edge) -> None:
        prev = edges.get(e.edge_id)
        if prev is None:
            edges[e.edge_id] = e
            return
        merged_props = dict(prev.props)
        merged_props.update(e.props)
        edges[e.edge_id] = Edge(
            edge_id=prev.edge_id,
            edge_type=prev.edge_type,
            src=prev.src,
            dst=prev.dst,
            weight=float(prev.weight) + float(e.weight),
            props=merged_props,
        )

    last_event_type_by_user: dict[str, Tuple[str, int]] = {}

    for me in mapped:
        user_key = f"{me.tenant_id}:{me.user_id}"
        user_node = _node(
            node_type=NodeType.USER.value,
            key=user_key,
            title=f"user:{me.user_id}",
            props={"tenant_id": me.tenant_id, "user_id": me.user_id},
        )
        upsert_node(user_node)

        et_key = me.event_type
        et_node = _node(
            node_type=NodeType.EVENT_TYPE.value,
            key=et_key,
            title=et_key,
            props={},
        )
        upsert_node(et_node)

        bump_edge(
            _edge(
                edge_type=EdgeType.DID.value,
                src=user_node.node_id,
                dst=et_node.node_id,
                weight=1.0,
                # FIX: no timestamp salt here — allows bump_edge to accumulate weight
                # (event frequency per user->event_type) correctly.
                props={"last_timestamp_ms": int(me.timestamp_ms)},
                salt="",
            )
        )

        if enable_sequence_edges:
            prev = last_event_type_by_user.get(user_key)
            if prev is not None:
                prev_et, prev_ts = prev
                prev_node = _node(node_type=NodeType.EVENT_TYPE.value, key=prev_et, title=prev_et, props={})
                upsert_node(prev_node)
                bump_edge(
                    _edge(
                        edge_type=EdgeType.FOLLOWS.value,
                        src=prev_node.node_id,
                        dst=et_node.node_id,
                        weight=1.0,
                        props={"user_id": me.user_id, "dt_ms": int(me.timestamp_ms) - int(prev_ts)},
                        salt=f"{user_key}:{prev_ts}->{me.timestamp_ms}",
                    )
                )
            last_event_type_by_user[user_key] = (me.event_type, int(me.timestamp_ms))

        for ent_type, ent_key in me.entities:
            ek = f"{ent_type}:{ent_key}"
            ent_node = _node(
                node_type=NodeType.ENTITY.value,
                key=ek,
                title=ek,
                props={"entity_type": ent_type, "entity_key": ent_key},
            )
            upsert_node(ent_node)

            bump_edge(
                _edge(
                    edge_type=EdgeType.TOUCHED.value,
                    src=user_node.node_id,
                    dst=ent_node.node_id,
                    weight=1.0,
                    # FIX: no timestamp salt — weight accumulates (touch frequency).
                    props={"last_timestamp_ms": int(me.timestamp_ms)},
                    salt="",
                )
            )
            bump_edge(
                _edge(
                    edge_type=EdgeType.MENTIONS.value,
                    src=et_node.node_id,
                    dst=ent_node.node_id,
                    weight=1.0,
                    # FIX: no timestamp salt — weight accumulates (mention frequency).
                    props={"last_timestamp_ms": int(me.timestamp_ms)},
                    salt="",
                )
            )

    meta = {"mapped_events": len(mapped), "nodes": len(nodes), "edges": len(edges)}
    return list(nodes.values()), list(edges.values()), meta
