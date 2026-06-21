from __future__ import annotations

from dataclasses import dataclass

DECISION_GRAPH_CONTRACT_VERSION = "1.0"
CANON_DECISION_GRAPH_CONTRACT = True


@dataclass(frozen=True)
class DecisionGraphNode:
    node_id: str
    kind: str


@dataclass(frozen=True)
class DecisionGraphEdge:
    source: str
    target: str
    relation: str


@dataclass(frozen=True)
class DecisionGraph:
    nodes: tuple[DecisionGraphNode, ...] = ()
    edges: tuple[DecisionGraphEdge, ...] = ()
    version: str = DECISION_GRAPH_CONTRACT_VERSION


__all__ = [
    "CANON_DECISION_GRAPH_CONTRACT",
    "DECISION_GRAPH_CONTRACT_VERSION",
    "DecisionGraph",
    "DecisionGraphEdge",
    "DecisionGraphNode",
]
