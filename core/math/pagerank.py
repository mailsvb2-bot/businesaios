from __future__ import annotations

from collections.abc import Mapping, Sequence


def pagerank(
    graph: Mapping[str, Sequence[str]],
    *,
    d: float = 0.85,
    iters: int = 50,
    tol: float = 1e-10,
) -> dict[str, float]:
    """PageRank-like:
      PR(A) = (1-d)/N + d * Σ PR(i)/L(i)
    """
    if d < 0 or d > 1:
        raise ValueError("d must be in [0,1].")
    nodes = set(graph.keys())
    for outs in graph.values():
        nodes.update(outs)
    nodes = list(nodes)
    n = len(nodes)
    if n == 0:
        return {}

    pr = {node: 1.0 / n for node in nodes}
    base = (1.0 - d) / n
    for _ in range(iters):
        new = {node: base for node in nodes}
        for i in nodes:
            outs = list(graph.get(i, ()))
            if not outs:
                share = d * (pr[i] / n)
                for node in nodes:
                    new[node] += share
            else:
                share = d * (pr[i] / len(outs))
                for j in outs:
                    new[j] += share
        diff = 0.0
        for node in nodes:
            diff += abs(new[node] - pr[node])
        pr = new
        if diff <= tol:
            break
    return pr
