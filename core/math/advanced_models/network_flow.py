from __future__ import annotations

from collections import deque
from typing import Dict, Tuple

Graph = dict[str, dict[str, float]]

def _bfs(residual: Graph, source: str, sink: str) -> dict[str, str] | None:
    parent: dict[str, str] = {}
    queue = deque([source])
    visited = {source}
    while queue:
        node = queue.popleft()
        for nb, cap in residual.get(node, {}).items():
            if nb not in visited and cap > 1e-12:
                visited.add(nb)
                parent[nb] = node
                if nb == sink:
                    return parent
                queue.append(nb)
    return None

def max_flow_edmonds_karp(graph: Graph, source: str, sink: str) -> tuple[float, Graph]:
    residual: Graph = {u: dict(vs) for u, vs in graph.items()}
    for u, vs in list(graph.items()):
        residual.setdefault(u, {})
        for v in vs:
            residual.setdefault(v, {})
            residual[v].setdefault(u, 0.0)

    max_flow = 0.0
    while True:
        parent = _bfs(residual, source, sink)
        if parent is None:
            break
        path_flow = float("inf")
        v = sink
        while v != source:
            u = parent[v]
            path_flow = min(path_flow, residual[u][v])
            v = u
        v = sink
        while v != source:
            u = parent[v]
            residual[u][v] -= path_flow
            residual[v][u] += path_flow
            v = u
        max_flow += path_flow
    return max_flow, residual
