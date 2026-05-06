from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from runtime.platform.event_store.sqlite_platform import SQLITE_ROW_FACTORY, SQLiteConnection, SQLiteRow, connect_sqlite
from tenancy.tenant_metrics_contract import (
    TenantMetricAggregate,
    TenantMetricPoint,
    TenantMetricsStoreContract,
    labels_signature,
    normalize_labels,
    utc_now,
)


CANON_TENANT_METRICS_SQLITE = True


def tenancy_metrics_sqlite_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_METRICS_SQLITE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("BUSINESAIOS_TENANCY_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "tenant_metrics.sqlite3"
    base = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(base) / "tenancy" / "tenant_metrics.sqlite3"


class SQLiteTenantMetricsStore(TenantMetricsStoreContract):
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else tenancy_metrics_sqlite_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_db()

    def append(self, point: TenantMetricPoint) -> TenantMetricPoint:
        point.validate()
        with self._lock, self._connect(write=True) as conn:
            conn.execute(
                "INSERT INTO tenant_metrics_points (tenant_id, metric_name, metric_type, value, emitted_at, labels_json) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    point.tenant_id,
                    point.metric_name,
                    point.metric_type,
                    float(point.value),
                    point.emitted_at.isoformat(),
                    json.dumps(dict(point.labels), sort_keys=True, separators=(",", ":")),
                ),
            )
        return point

    def increment(self, *, tenant_id: str, metric_name: str, amount: float = 1.0, labels: Mapping[str, str] | None = None, emitted_at: datetime | None = None) -> TenantMetricPoint:
        point = TenantMetricPoint(
            tenant_id=require_tenant_id(tenant_id),
            metric_name=str(metric_name).strip(),
            value=float(amount),
            metric_type="counter",
            emitted_at=emitted_at or utc_now(),
            labels=normalize_labels(labels),
        )
        return self.append(point)

    def list_points(self, *, tenant_id: str, metric_name: str | None = None, since: datetime | None = None) -> tuple[TenantMetricPoint, ...]:
        tid = require_tenant_id(tenant_id)
        clauses = ["tenant_id = ?"]
        params: list[object] = [tid]
        if metric_name is not None:
            clauses.append("metric_name = ?")
            params.append(str(metric_name).strip())
        if since is not None:
            if since.tzinfo is None or since.utcoffset() is None:
                raise ValueError("since must be timezone-aware")
            clauses.append("emitted_at >= ?")
            params.append(since.isoformat())
        sql = (
            "SELECT tenant_id, metric_name, metric_type, value, emitted_at, labels_json FROM tenant_metrics_points WHERE "
            + " AND ".join(clauses)
            + " ORDER BY emitted_at, metric_name, labels_json"
        )
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        points: list[TenantMetricPoint] = []
        for row in rows:
            point = TenantMetricPoint(
                tenant_id=row[0],
                metric_name=row[1],
                metric_type=row[2],
                value=float(row[3]),
                emitted_at=datetime.fromisoformat(row[4]),
                labels=json.loads(row[5] or "{}"),
            )
            point.validate()
            points.append(point)
        return tuple(points)

    def aggregate(self, *, tenant_id: str, metric_name: str, since: datetime | None = None) -> TenantMetricAggregate | None:
        points = list(self.list_points(tenant_id=tenant_id, metric_name=metric_name, since=since))
        if not points:
            return None
        last = points[-1]
        values = [float(point.value) for point in points]
        signatures = {labels_signature(point.labels) for point in points}
        aggregate = TenantMetricAggregate(
            tenant_id=last.tenant_id,
            metric_name=last.metric_name,
            sample_count=len(points),
            total=float(sum(values)),
            minimum=float(min(values)),
            maximum=float(max(values)),
            last_value=float(last.value),
            last_emitted_at=last.emitted_at,
            labels=dict(last.labels),
            label_series_count=len(signatures),
            labels_collapsed=len(signatures) > 1,
        )
        aggregate.validate()
        return aggregate

    def _connect(self, *, write: bool = False) -> SQLiteConnection:
        conn = connect_sqlite(self._path, timeout=30.0, isolation_level=None)
        conn.row_factory = SQLITE_ROW_FACTORY
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        return conn


    def schema_version(self) -> int:
        return 1

    def read_backend_clock(self) -> datetime:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')").fetchone()
        return utc_now() if row is None else datetime.fromisoformat(str(row[0]).replace('Z', '+00:00'))

    def _init_db(self) -> None:
        with self._lock, self._connect(write=True) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tenant_metrics_points ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, metric_name TEXT NOT NULL, metric_type TEXT NOT NULL, value REAL NOT NULL, emitted_at TEXT NOT NULL, labels_json TEXT NOT NULL)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_tenant_metrics_points_scope ON tenant_metrics_points(tenant_id, metric_name, emitted_at)")


__all__ = ["CANON_TENANT_METRICS_SQLITE", "SQLiteTenantMetricsStore", "tenancy_metrics_sqlite_path"]
