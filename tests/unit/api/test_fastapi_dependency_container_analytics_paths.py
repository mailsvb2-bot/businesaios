from __future__ import annotations

from dataclasses import dataclass, field

from adapters.api.fastapi.dependencies import FastAPIDependencyContainer
from observability.metrics import InMemoryMetrics


@dataclass(frozen=True)
class _BootResultStub:
    runtime: object
    decision_application: object = object()
    startup_report: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RuntimeStub:
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)


def test_dependency_container_exposes_analytics_paths():
    container = FastAPIDependencyContainer(boot_result=_BootResultStub(runtime=_RuntimeStub()))
    assert str(container.analytics_snapshot_db_path()).endswith('analytics_snapshots.sqlite3')
    assert str(container.analytics_manifest_chain_db_path()).endswith('analytics_manifest_chain.sqlite3')
    assert str(container.analytics_export_root()).endswith('observability/exports/analytics')
