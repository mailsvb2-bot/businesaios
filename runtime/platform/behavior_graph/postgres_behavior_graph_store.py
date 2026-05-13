from __future__ import annotations

import json
from typing import Any, Dict, Optional

from contracts.behavior_graph import Edge, GraphSnapshot, Neighbor, Node, PathStep
from observability.platform.observability.silent import swallow
from runtime.platform.postgres_port import PostgresPort


class PostgresBehaviorGraphStore:
    """Durable behavior graph store (postgres)."""

    def __init__(self, dsn: str):
        self._dsn = str(dsn)
        self._port: PostgresPort | None = None

    def __enter__(self) -> "PostgresBehaviorGraphStore":
        self._port = PostgresPort(self._dsn, application_name="businesaios-behavior-graph").__enter__()
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._port is not None
        self._port.__exit__(exc_type, exc, tb)
        self._port = None

    def ping(self) -> bool:
        """Return true when the sealed Postgres behavior-graph store connection is alive."""
        try:
            if self._port is None:
                return False
            return bool(self._port.ping())
        except Exception:
            return False

    def _init_schema(self) -> None:
        assert self._port is not None
        self._port.execute(
            """
            CREATE TABLE IF NOT EXISTS behavior_graph_snapshots (
              tenant_id TEXT NOT NULL,
              scope TEXT NOT NULL,
              built_at_ms BIGINT NOT NULL,
              meta_json TEXT NOT NULL,
              PRIMARY KEY (tenant_id, scope)
            );
            """
        )
        self._port.execute(
            """
            CREATE TABLE IF NOT EXISTS behavior_graph_nodes (
              tenant_id TEXT NOT NULL,
              scope TEXT NOT NULL,
              node_id TEXT NOT NULL,
              node_type TEXT NOT NULL,
              key TEXT NOT NULL,
              title TEXT NOT NULL,
              props_json TEXT NOT NULL,
              PRIMARY KEY (tenant_id, scope, node_id)
            );
            """
        )
        self._port.execute(
            """
            CREATE TABLE IF NOT EXISTS behavior_graph_edges (
              tenant_id TEXT NOT NULL,
              scope TEXT NOT NULL,
              edge_id TEXT NOT NULL,
              edge_type TEXT NOT NULL,
              src TEXT NOT NULL,
              dst TEXT NOT NULL,
              weight DOUBLE PRECISION NOT NULL,
              props_json TEXT NOT NULL,
              PRIMARY KEY (tenant_id, scope, edge_id)
            );
            """
        )
        self._port.execute("CREATE INDEX IF NOT EXISTS idx_bg_edges_src ON behavior_graph_edges(tenant_id, scope, src)")
        self._port.execute("CREATE INDEX IF NOT EXISTS idx_bg_edges_dst ON behavior_graph_edges(tenant_id, scope, dst)")
        self._port.execute("CREATE INDEX IF NOT EXISTS idx_bg_edges_type ON behavior_graph_edges(tenant_id, scope, edge_type)")

    def upsert_snapshot(
        self,
        *,
        tenant_id: str,
        scope: str,
        built_at_ms: int,
        nodes: list[Node],
        edges: list[Edge],
        meta: Dict[str, Any] | None = None,
    ) -> None:
        assert self._port is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        if not tid or not sc:
            raise ValueError("tenant_id and scope are required")
        meta_obj = dict(meta or {})
        meta_obj["built_at_ms"] = int(built_at_ms)
        meta_json = json.dumps(meta_obj, ensure_ascii=False)

        # Replace-by-scope for determinism. Keep transaction control inside
        # the sealed PostgresPort boundary: execute + explicit commit/rollback.
        try:
            self._port.execute(
                "INSERT INTO behavior_graph_snapshots(tenant_id, scope, built_at_ms, meta_json) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT(tenant_id, scope) DO UPDATE SET built_at_ms=EXCLUDED.built_at_ms, meta_json=EXCLUDED.meta_json",
                (tid, sc, int(built_at_ms), meta_json),
            )
            self._port.execute("DELETE FROM behavior_graph_nodes WHERE tenant_id=%s AND scope=%s", (tid, sc))
            self._port.execute("DELETE FROM behavior_graph_edges WHERE tenant_id=%s AND scope=%s", (tid, sc))

            for n in nodes:
                self._port.execute(
                    "INSERT INTO behavior_graph_nodes(tenant_id, scope, node_id, node_type, key, title, props_json) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (
                        tid,
                        sc,
                        n.node_id,
                        str(n.node_type),
                        str(n.key),
                        str(n.title),
                        json.dumps(n.props or {}, ensure_ascii=False),
                    ),
                )

            for e in edges:
                self._port.execute(
                    "INSERT INTO behavior_graph_edges(tenant_id, scope, edge_id, edge_type, src, dst, weight, props_json) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        tid,
                        sc,
                        e.edge_id,
                        str(e.edge_type),
                        str(e.src),
                        str(e.dst),
                        float(e.weight),
                        json.dumps(e.props or {}, ensure_ascii=False),
                    ),
                )

            self._port.commit()
        except Exception:
            self._port.rollback()
            raise

    def get_snapshot(self, *, tenant_id: str, scope: str) -> Optional[GraphSnapshot]:
        assert self._port is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        row = self._port.fetchone(
            "SELECT built_at_ms, meta_json FROM behavior_graph_snapshots WHERE tenant_id=%s AND scope=%s",
            (tid, sc),
        )
        if not row:
            return None
        built_at_ms = int(row[0])
        meta = json.loads(row[1]) if row[1] else {}

        nrows = self._port.fetchall(
            "SELECT node_id,node_type,key,title,props_json FROM behavior_graph_nodes WHERE tenant_id=%s AND scope=%s",
            (tid, sc),
        )
        erows = self._port.fetchall(
            "SELECT edge_id,edge_type,src,dst,weight,props_json FROM behavior_graph_edges WHERE tenant_id=%s AND scope=%s",
            (tid, sc),
        )
        nodes = [Node(node_id=r[0], node_type=r[1], key=r[2], title=r[3], props=(json.loads(r[4]) if r[4] else {})) for r in nrows]
        edges = [Edge(edge_id=r[0], edge_type=r[1], src=r[2], dst=r[3], weight=float(r[4]), props=(json.loads(r[5]) if r[5] else {})) for r in erows]
        return GraphSnapshot(tenant_id=tid, scope=sc, built_at_ms=built_at_ms, nodes=nodes, edges=edges, meta=meta)

    def get_node(self, *, tenant_id: str, scope: str, node_id: str) -> Optional[Node]:
        assert self._port is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        nid = str(node_id).strip()
        row = self._port.fetchone(
            "SELECT node_id,node_type,key,title,props_json FROM behavior_graph_nodes WHERE tenant_id=%s AND scope=%s AND node_id=%s",
            (tid, sc, nid),
        )
        if not row:
            return None
        return Node(node_id=row[0], node_type=row[1], key=row[2], title=row[3], props=(json.loads(row[4]) if row[4] else {}))

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
        assert self._port is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        nid = str(node_id).strip()
        d = str(direction or "out").strip().lower()
        lim = max(1, min(int(limit), 500))
        et = str(edge_type).strip() if edge_type else None
        if d not in {"out", "in"}:
            raise ValueError("direction must be 'out' or 'in'")

        if d == "out":
            q = "SELECT edge_id,edge_type,src,dst,weight,props_json FROM behavior_graph_edges WHERE tenant_id=%s AND scope=%s AND src=%s"
        else:
            q = "SELECT edge_id,edge_type,src,dst,weight,props_json FROM behavior_graph_edges WHERE tenant_id=%s AND scope=%s AND dst=%s"
        params: list[Any] = [tid, sc, nid]
        if et:
            q += " AND edge_type=%s"
            params.append(et)
        q += " ORDER BY weight DESC LIMIT %s"
        params.append(lim)
        rows = self._port.fetchall(q, tuple(params))
        out: list[Neighbor] = []
        for r in rows:
            other = r[3] if d == "out" else r[2]
            out.append(Neighbor(node_id=str(other), weight=float(r[4]), edge_type=str(r[1]), edge_id=str(r[0]), props=(json.loads(r[5]) if r[5] else {})))
        return out

    def shortest_path(
        self,
        *,
        tenant_id: str,
        scope: str,
        src: str,
        dst: str,
        max_hops: int = 6,
    ) -> list[PathStep]:
        # Keep implementation simple: load outgoing edges for visited nodes.
        assert self._port is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        s = str(src).strip()
        t = str(dst).strip()
        mh = max(1, min(int(max_hops), 12))
        if s == t:
            return [PathStep(node_id=s, via_edge_id=None, via_edge_type=None, weight=0.0)]

        from collections import deque

        q = deque([(s, 0)])
        prev: dict[str, tuple[str, str, str, float]] = {}
        seen = {s}

        while q:
            cur, depth = q.popleft()
            if depth >= mh:
                continue
            rows = self._port.fetchall(
                "SELECT edge_id,edge_type,src,dst,weight FROM behavior_graph_edges WHERE tenant_id=%s AND scope=%s AND src=%s",
                (tid, sc, cur),
            )
            for r in rows:
                nxt = str(r[3])
                if nxt in seen:
                    continue
                seen.add(nxt)
                prev[nxt] = (cur, str(r[0]), str(r[1]), float(r[4]))
                if nxt == t:
                    q.clear()
                    break
                q.append((nxt, depth +1))

        if t not in prev:
            return []

        steps: list[PathStep] = [PathStep(node_id=t, via_edge_id=prev[t][1], via_edge_type=prev[t][2], weight=float(prev[t][3]))]
        cur = t
        while cur != s:
            p = prev[cur]
            cur = p[0]
            if cur == s:
                steps.append(PathStep(node_id=cur, via_edge_id=None, via_edge_type=None, weight=0.0))
                break
            pp = prev.get(cur)
            if pp is None:
                steps.append(PathStep(node_id=cur, via_edge_id=None, via_edge_type=None, weight=0.0))
                break
            steps.append(PathStep(node_id=cur, via_edge_id=pp[1], via_edge_type=pp[2], weight=float(pp[3])))
        steps.reverse()
        return steps

    def reset(self, *, tenant_id: str, scope: str) -> None:
        assert self._port is not None
        tid = str(tenant_id).strip()
        sc = str(scope).strip()
        with self._port.transaction():
            self._port.execute("DELETE FROM behavior_graph_edges WHERE tenant_id=%s AND scope=%s", (tid, sc))
            self._port.execute("DELETE FROM behavior_graph_nodes WHERE tenant_id=%s AND scope=%s", (tid, sc))
            self._port.execute("DELETE FROM behavior_graph_snapshots WHERE tenant_id=%s AND scope=%s", (tid, sc))
