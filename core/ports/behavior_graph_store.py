from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from contracts.behavior_graph import Edge, GraphSnapshot, Neighbor, Node, PathStep


@dataclass(frozen=True)
class BehaviorGraphQuery:
    tenant_id: str
    scope: str


class BehaviorGraphStore(Protocol):
    def upsert_snapshot(
        self,
        *,
        tenant_id: str,
        scope: str,
        built_at_ms: int,
        nodes: list[Node],
        edges: list[Edge],
        meta: dict[str, Any] | None = None,
    ) -> None:
        ...

    def get_snapshot(self, *, tenant_id: str, scope: str) -> GraphSnapshot | None:
        ...

    def get_node(self, *, tenant_id: str, scope: str, node_id: str) -> Node | None:
        ...

    def neighbors(
        self,
        *,
        tenant_id: str,
        scope: str,
        node_id: str,
        direction: str = "out",
        limit: int = 50,
        edge_type: str | None = None,
    ) -> list[Neighbor]:
        ...

    def shortest_path(
        self,
        *,
        tenant_id: str,
        scope: str,
        src: str,
        dst: str,
        max_hops: int = 6,
    ) -> list[PathStep]:
        ...

    def reset(self, *, tenant_id: str, scope: str) -> None:
        ...
