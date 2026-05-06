from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

CANON_CLICKHOUSE_EXPORTER = True


class ClickHouseClientProtocol:
    def command(self, sql: str, *args: Any, **kwargs: Any) -> Any: ...
    def insert(self, table: str, data: list[tuple[Any, ...]], column_names: list[str]) -> Any: ...


@dataclass(frozen=True)
class ClickHouseExporterConfig:
    endpoint: str
    database: str
    table: str = 'platform_events'
    username: str | None = None
    password: str | None = None
    secure: bool = True

    def validate(self) -> None:
        if not str(self.endpoint or '').strip():
            raise ValueError('endpoint is required')
        if not str(self.database or '').strip():
            raise ValueError('database is required')
        if not str(self.table or '').strip():
            raise ValueError('table is required')


@dataclass(frozen=True)
class ClickHouseExporter:
    client: ClickHouseClientProtocol
    config: ClickHouseExporterConfig

    def __post_init__(self) -> None:
        self.config.validate()

    def healthcheck(self, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {'status': 'ready_for_credentials', 'backend': 'clickhouse', 'database': self.config.database, 'table': self.config.table}
        self.client.command('SELECT 1')
        return {'status': 'ok', 'backend': 'clickhouse', 'database': self.config.database, 'table': self.config.table}

    def export_events(self, *, rows: Iterable[Mapping[str, Any]], dry_run: bool = False) -> dict[str, Any]:
        materialized = [dict(item) for item in rows]
        if dry_run:
            return {'status': 'prepared', 'row_count': len(materialized), 'table': self.config.table}
        if not materialized:
            return {'status': 'noop', 'row_count': 0, 'table': self.config.table}
        columns = sorted(materialized[0].keys())
        data = [tuple(item.get(column) for column in columns) for item in materialized]
        self.client.insert(self.config.table, data, columns)
        return {'status': 'exported', 'row_count': len(materialized), 'table': self.config.table}
