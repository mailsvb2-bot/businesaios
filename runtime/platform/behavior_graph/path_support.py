"""Passive path reconstruction shared by behavior-graph persistence adapters.

This module contains no policy selection, action choice, learning, planning or
effect execution. It only projects a predecessor map produced by a store query
into the public ``PathStep`` contract so SQLite and PostgreSQL cannot drift.
"""

from __future__ import annotations

from contracts.behavior_graph import PathStep

CANON_BEHAVIOR_GRAPH_PATH_PROJECTION = True


def finish_shortest_path(
    *,
    prev: dict[str, tuple[str, str, str, float]],
    src: str,
    dst: str,
) -> list[PathStep]:
    if dst not in prev:
        return []
    steps = [
        PathStep(
            node_id=dst,
            via_edge_id=prev[dst][1],
            via_edge_type=prev[dst][2],
            weight=float(prev[dst][3]),
        )
    ]
    cur = dst
    while cur != src:
        parent, _edge_id, _edge_type, _weight = prev[cur]
        cur = parent
        if cur == src:
            steps.append(PathStep(node_id=cur, via_edge_id=None, via_edge_type=None, weight=0.0))
            break
        previous = prev.get(cur)
        if previous is None:
            steps.append(PathStep(node_id=cur, via_edge_id=None, via_edge_type=None, weight=0.0))
            break
        steps.append(
            PathStep(
                node_id=cur,
                via_edge_id=previous[1],
                via_edge_type=previous[2],
                weight=float(previous[3]),
            )
        )
    steps.reverse()
    return steps


__all__ = ["CANON_BEHAVIOR_GRAPH_PATH_PROJECTION", "finish_shortest_path"]
