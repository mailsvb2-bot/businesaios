from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Mapping, Sequence


def cosine_similarity(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    """Sparse cosine similarity for embeddings / co-occurrence vectors."""
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for k, va in a.items():
        na += float(va) * float(va)
        if k in b:
            dot += float(va) * float(b[k])
    for vb in b.values():
        nb += float(vb) * float(vb)
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / math.sqrt(na * nb)


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return 0.0 if union == 0 else (inter / union)


def random_walk(
    graph: Mapping[str, Sequence[str]],
    start: str,
    *,
    steps: int = 10,
    restart_p: float = 0.0,
) -> list[str]:
    """Random walk for recommendation / discovery."""
    if steps <= 0:
        return [start]
    if restart_p < 0 or restart_p > 1:
        raise ValueError("restart_p must be in [0,1].")
    path = [start]
    cur = start
    for _ in range(steps):
        if restart_p > 0 and random.random() < restart_p:
            cur = start
            path.append(cur)
            continue
        neigh = list(graph.get(cur, []))
        if not neigh:
            break
        cur = random.choice(neigh)
        path.append(cur)
    return path


def cooccurrence_recommendations(
    user_to_items: Mapping[str, Sequence[str]],
    *,
    top_k: int = 10,
) -> dict[str, list[tuple[str, float]]]:
    """Simple graph-based recommender (User->Item bipartite projection)."""
    co = defaultdict(lambda: defaultdict(int))
    user_sets: dict[str, set[str]] = {u: set(items) for u, items in user_to_items.items()}
    for items in user_sets.values():
        li = list(items)
        for i in range(len(li)):
            for j in range(i + 1, len(li)):
                a, b = li[i], li[j]
                co[a][b] += 1
                co[b][a] += 1

    out: dict[str, list[tuple[str, float]]] = {}
    for u, seen in user_sets.items():
        scores = defaultdict(float)
        for it in seen:
            for cand, c in co.get(it, {}).items():
                if cand in seen:
                    continue
                scores[cand] += float(c)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[: max(0, top_k)]
        out[u] = ranked
    return out
