"""Behavior Graph (core).

Deterministic primitives to build a lightweight behavior graph
from an event stream.
"""

from core.behavior_graph.builder import build_behavior_graph_from_events
from core.behavior_graph.ids import canonical_edge_id, canonical_node_id

__all__ = [
    "build_behavior_graph_from_events",
    "canonical_node_id",
    "canonical_edge_id",
]
