from __future__ import annotations

"""Behavior Graph contract types.

This module intentionally lives in `contracts/` to avoid cross-layer coupling.
Runtime/UI can depend on this module without importing `core.*`.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    USER = "user"
    EVENT_TYPE = "event_type"
    ENTITY = "entity"


class EdgeType(str, Enum):
    DID = "did"  # user -> event_type
    TOUCHED = "touched"  # user -> entity
    MENTIONS = "mentions"  # event_type -> entity
    FOLLOWS = "follows"  # event_type -> event_type (sequence)


@dataclass(frozen=True)
class Node:
    node_id: str
    node_type: str
    key: str
    title: str
    props: dict[str, Any]


@dataclass(frozen=True)
class Edge:
    edge_id: str
    edge_type: str
    src: str
    dst: str
    weight: float
    props: dict[str, Any]


@dataclass(frozen=True)
class GraphSnapshot:
    tenant_id: str
    scope: str
    built_at_ms: int
    nodes: list[Node]
    edges: list[Edge]
    meta: dict[str, Any]


@dataclass(frozen=True)
class Neighbor:
    node_id: str
    weight: float
    edge_type: str
    edge_id: str
    props: dict[str, Any]


@dataclass(frozen=True)
class PathStep:
    node_id: str
    via_edge_id: str | None
    via_edge_type: str | None
    weight: float
