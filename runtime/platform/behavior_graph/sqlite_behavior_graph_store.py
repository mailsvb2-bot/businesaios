from __future__ import annotations

"""Canonical sqlite behavior graph store.

This module owns the SQLite implementation directly. Historical split modules
(``*_part1``/``*_part2``) are no longer owners
the package installs compat
aliases for those imports. Keeping the full implementation here removes a real
risk where the canonical surface pointed at a truncated part file.
"""

import json
import sqlite3
from collections import deque
from typing import Any

from contracts.behavior_graph import Edge, GraphSnapshot, Neighbor, Node, PathStep
from observability.platform.observability.silent import swallow
from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env

CANON_BEHAVIOR_GRAPH_SQLITE_OWNER = True


def finish_shortest_path(*, prev:
    dict[str, tuple[str, str, str, float]], src: str, dst: str) -> list[PathStep]:
    if dst not in prev:
        return []
    steps: list[PathStep] = [
        PathStep(node_id=dst, via_edge_id=prev[dst][1], via_edge_type=prev[dst][2], weight=float(prev[dst][3]))
    ]
    cur = dst
    while cur != src:
        p = prev[cur]
        cur = p[0]
        if cur == src:
            steps.append(PathStep(node_id=cur, via_edge_id=None, via_edge_type=None, weight=0.0))
            break
        pp = prev.get(cur)
        if pp is None:
            steps.append(PathStep(node_id=cur, via_edge_id=None, via_edge_type=None, weight=0.0))
            break
        steps.append(PathStep(node_id=cur, via_edge_id=pp[1], via_edge_type=pp[2], weight=float(pp[3])))
    steps.reverse()
    return steps


def rollback_reset(*, db:
    sqlite3.Connection, tenant_id: str, scope: str) -> None:
    cur = db.cursor()
    try:
        cur.execute("DELETE FROM behavior_graph_edges WHERE tenant_id=? AND scope=?", (tenant_id, scope))
        cur.execute("DELETE FROM behavior_graph_nodes WHERE tenant_id=? AND scope=?", (tenant_id, scope))
        cur.execute("DELETE FROM behavior_graph_snapshots WHERE tenant_id=? AND scope=?", (tenant_id, scope))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            swallow(__name__, "sqlite_behavior_graph.reset.rollback")
        raise


class SqliteBehaviorGraphStore:
    """Durable behavior graph store (sqlite)."""

    def __init__(self, path:
        str):
        self._path = str(path)
        self._db: sqlite3.Connection | None = None

    def __enter__(self) -> SqliteBehaviorGraphStore:
        self._db = sqlite3.connect(self._path, timeout=5.0, check_same_thread=False)
        configure_sqlite(self._db, prod=is_prod_env())
        self._db.execute("PRAGMA journal_mode=WAL;")
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._db is None:
            return
        try:
            self._db.commit()
        except Exception:
            swallow(__name__, "sqlite_behavior_graph.commit")
        try:
            self._db.close()
        except Exception:
            swallow(__name__, "sqlite_behavior_graph.close")
        self._db = None

    def _init_schema(self) -> None:
        assert self._db is not None
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS behavior_graph_snapshots ("
            "tenant_id TEXT NOT NULL, "
            "scope TEXT NOT NULL, "
            "built_at_ms INTEGER NOT NULL, "
            "meta_json TEXT NOT NULL, "
            "PRIMARY KEY (tenant_id, scope))"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS behavior_graph_nodes ("
            "tenant_id TEXT NOT NULL, "
            "scope TEXT NOT NULL, "
            "node_id TEXT NOT NULL, "
            "node_type TEXT NOT NULL, "
            "key TEXT NOT NULL, "
            "title TEXT NOT NULL, "
            "props_json TEXT NOT NULL, "
            "PRIMARY KEY (tenant_id, scope, node_id))"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS behavior_graph_edges ("
            "tenant_id TEXT NOT NULL, "
            "scope TEXT NOT NULL, "
            "edge_id TEXT NOT NULL, "
            "edge_type TEXT NOT NULL, "
            "src TEXT NOT NULL, "
            "dst TEXT NOT NULL, "
            "weight REAL NOT NULL, "
            "props_json TEXT NOT NULL, "
            "PRIMARY KEY (tenant_id, scope, edge_id))"
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_bg_edges_src ON behavior_graph_edges(tenant_id, scope, src)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_bg_edges_dst ON behavior_graph_edges(tenant_id, scope, dst)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_bg_edges_type ON behavior_graph_edges(tenant_id, scope, edge_type)")
        self._db.commit()

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
        assert self._db is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        if not tid or not sc:
            raise ValueError("tenant_id and scope are required")

        meta_obj = dict(meta or {})
        meta_obj["built_at_ms"] = int(built_at_ms)
        meta_json = json.dumps(meta_obj, ensure_ascii=False)

        cur = self._db.cursor()
        try:
            cur.execute(
                "INSERT INTO behavior_graph_snapshots(tenant_id, scope, built_at_ms, meta_json) "
                "VALUES(?,?,?,?) "
                "ON CONFLICT(tenant_id, scope) DO UPDATE SET built_at_ms=excluded.built_at_ms, meta_json=excluded.meta_json",
                (tid, sc, int(built_at_ms), meta_json),
            )
            cur.execute("DELETE FROM behavior_graph_nodes WHERE tenant_id=? AND scope=?", (tid, sc))
            cur.execute("DELETE FROM behavior_graph_edges WHERE tenant_id=? AND scope=?", (tid, sc))
            cur.executemany(
                "INSERT INTO behavior_graph_nodes(tenant_id, scope, node_id, node_type, key, title, props_json) VALUES(?,?,?,?,?,?,?)",
                [
                    (
                        tid,
                        sc,
                        n.node_id,
                        str(n.node_type),
                        str(n.key),
                        str(n.title),
                        json.dumps(n.props or {}, ensure_ascii=False),
                    )
                    for n in nodes
                ],
            )
            cur.executemany(
                "INSERT INTO behavior_graph_edges(tenant_id, scope, edge_id, edge_type, src, dst, weight, props_json) VALUES(?,?,?,?,?,?,?,?)",
                [
                    (
                        tid,
                        sc,
                        e.edge_id,
                        str(e.edge_type),
                        str(e.src),
                        str(e.dst),
                        float(e.weight),
                        json.dumps(e.props or {}, ensure_ascii=False),
                    )
                    for e in edges
                ],
            )
            self._db.commit()
        except Exception:
            try:
                self._db.rollback()
            except Exception:
                swallow(__name__, "sqlite_behavior_graph.rollback")
            raise

    def get_snapshot(self, *, tenant_id:
        str, scope: str) -> GraphSnapshot | None:
        assert self._db is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        row = self._db.execute(
            "SELECT built_at_ms, meta_json FROM behavior_graph_snapshots WHERE tenant_id=? AND scope=?",
            (tid, sc),
        ).fetchone()
        if not row:
            return None
        built_at_ms = int(row[0])
        meta = json.loads(row[1]) if row[1] else {}
        nrows = self._db.execute(
            "SELECT node_id,node_type,key,title,props_json FROM behavior_graph_nodes WHERE tenant_id=? AND scope=?",
            (tid, sc),
        ).fetchall()
        erows = self._db.execute(
            "SELECT edge_id,edge_type,src,dst,weight,props_json FROM behavior_graph_edges WHERE tenant_id=? AND scope=?",
            (tid, sc),
        ).fetchall()
        nodes = [Node(node_id=r[0], node_type=r[1], key=r[2], title=r[3], props=(json.loads(r[4]) if r[4] else {})) for r in nrows]
        edges = [Edge(edge_id=r[0], edge_type=r[1], src=r[2], dst=r[3], weight=float(r[4]), props=(json.loads(r[5]) if r[5] else {})) for r in erows]
        return GraphSnapshot(tenant_id=tid, scope=sc, built_at_ms=built_at_ms, nodes=nodes, edges=edges, meta=meta)

    def get_node(self, *, tenant_id:
        str, scope: str, node_id: str) -> Node | None:
        assert self._db is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        nid = str(node_id).strip()
        row = self._db.execute(
            "SELECT node_id,node_type,key,title,props_json FROM behavior_graph_nodes WHERE tenant_id=? AND scope=? AND node_id=?",
            (tid, sc, nid),
        ).fetchone()
        if not row:
            return None
        return Node(node_id=row[0], node_type=row[1], key=row[2], title=row[3], props=(json.loads(row[4]) if row[4] else {}))

    def neighbors(self, *, tenant_id:
        str, scope: str, node_id: str, direction: str = "out", limit: int = 50, edge_type: str | None = None) -> list[Neighbor]:
        assert self._db is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        nid = str(node_id).strip()
        d = str(direction or "out").strip().lower()
        lim = max(1, min(int(limit), 500))
        et = str(edge_type).strip() if edge_type else None
        if d not in {"out", "in"}:
            raise ValueError("direction must be 'out' or 'in'")
        base = "SELECT edge_id,edge_type,src,dst,weight,props_json FROM behavior_graph_edges WHERE tenant_id=? AND scope=? AND "
        params = [tid, sc]
        base += "src=?" if d == "out" else "dst=?"
        params.append(nid)
        if et:
            base += " AND edge_type=?"
            params.append(et)
        base += " ORDER BY weight DESC LIMIT ?"
        params.append(lim)
        rows = self._db.execute(base, tuple(params)).fetchall()
        out: list[Neighbor] = []
        for r in rows:
            other = r[3] if d == "out" else r[2]
            out.append(Neighbor(node_id=str(other), weight=float(r[4]), edge_type=str(r[1]), edge_id=str(r[0]), props=(json.loads(r[5]) if r[5] else {})))
        return out

    def shortest_path(self, *, tenant_id:
        str, scope: str, src: str, dst: str, max_hops: int = 6) -> list[PathStep]:
        assert self._db is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        s = str(src).strip()
        t = str(dst).strip()
        mh = max(1, min(int(max_hops), 12))
        if s == t:
            return [PathStep(node_id=s, via_edge_id=None, via_edge_type=None, weight=0.0)]
        q = deque([(s, 0)])
        prev: dict[str, tuple[str, str, str, float]] = {}
        seen = {s}
        while q:
            cur, depth = q.popleft()
            if depth >= mh:
                continue
            rows = self._db.execute(
                "SELECT edge_id,edge_type,src,dst,weight FROM behavior_graph_edges WHERE tenant_id=? AND scope=? AND src=?",
                (tid, sc, cur),
            ).fetchall()
            for r in rows:
                nxt = str(r[3])
                if nxt in seen:
                    continue
                seen.add(nxt)
                prev[nxt] = (cur, str(r[0]), str(r[1]), float(r[4]))
                if nxt == t:
                    q.clear()
                    break
                q.append((nxt, depth + 1))
        return finish_shortest_path(prev=prev, src=s, dst=t)

    def reset(self, *, tenant_id:
        str, scope: str) -> None:
        assert self._db is not None
        rollback_reset(db=self._db, tenant_id=str(tenant_id).strip(), scope=str(scope).strip())


__all__ = [
    "CANON_BEHAVIOR_GRAPH_SQLITE_OWNER",
    "SqliteBehaviorGraphStore",
    "finish_shortest_path",
    "rollback_reset",
]
