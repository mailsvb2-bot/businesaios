from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from deployment.readiness_checks import build_default_readiness_registry, snapshot_runtime_readiness
from deployment.version_manifest import VersionManifestBuilder
from entrypoints.api.health_models import HealthCheckView, HealthResponse


@dataclass(frozen=True)
class HealthHandler:
    application_service: object
    startup_report: tuple[str, ...] = ()
    runtime_orchestrator: object | None = None
    repo_root: str = "."
    service_name: str = "businesaios"

    def health(self) -> HealthResponse:
        events = self._events()
        report = self._report(events=events)
        return HealthResponse(
            status='ok' if report['status'] != 'fail' else 'degraded',
            startup_audit_events=list(events),
            checks=list(report['checks']),
            details=dict(report['details']),
        )

    def readiness(self) -> HealthResponse:
        events = self._events()
        report = self._report(events=events)
        return HealthResponse(
            status='ready' if self._is_ready(report, events=events) else 'degraded',
            startup_audit_events=list(events),
            checks=list(report['checks']),
            details=dict(report['details']),
        )

    def storage(self) -> HealthResponse:
        events = self._events()
        report = self._report(events=events)
        return HealthResponse(
            status='ready' if self._is_storage_ready(report, events=events) else 'degraded',
            startup_audit_events=list(events),
            checks=list(report['checks']),
            details={**dict(report['details']), 'surface': 'storagez'},
        )

    def execution(self) -> HealthResponse:
        events = self._events()
        report = self._report(events=events)
        return HealthResponse(
            status='ready' if self._is_execution_ready(report, events=events) else 'degraded',
            startup_audit_events=list(events),
            checks=list(report['checks']),
            details={**dict(report['details']), 'surface': 'executionz'},
        )

    def _events(self) -> tuple[str, ...]:
        producer = getattr(self.application_service, 'startup_audit_events', None)
        if callable(producer):
            events = producer()
            return tuple(str(item) for item in (events or ()))
        return tuple(str(item) for item in self.startup_report)

    def _report(self, *, events: tuple[str, ...]) -> dict[str, object]:
        checks: list[HealthCheckView] = []
        details: dict[str, object] = {}
        details['startup_events_count'] = len(events)
        details.update(self._version_details())
        orchestrator = self.runtime_orchestrator
        if self._looks_like_runtime_orchestrator(orchestrator):
            registry = build_default_readiness_registry(orchestrator)
            health = registry.run_all(
                service=self.service_name,
                version=details.get('version'),
                release_id=details.get('release_tag'),
            )
            snapshot = snapshot_runtime_readiness(orchestrator)
            checks.extend(HealthCheckView(**item.to_dict()) for item in health.checks)
            details['runtime_readiness'] = snapshot.to_dict()
            details['health_overall_status'] = health.overall_status.value
            details['runtime_orchestrator_present'] = True
        if 'runtime_orchestrator_present' not in details:
            details['runtime_orchestrator_present'] = False
        return {
            'status': self._overall_status(checks),
            'checks': checks,
            'details': details,
        }

    def _version_details(self) -> dict[str, object]:
        try:
            manifest = VersionManifestBuilder(service=self.service_name, repo_root=self.repo_root).build()
            return {
                'version': manifest.build.version,
                'release_tag': manifest.build.release_tag,
                'constitution_version': manifest.constitution_version,
                'release_manifest_file_count': manifest.release_manifest_file_count,
            }
        except Exception as exc:
            return {
                'version_error': f'{type(exc).__name__}: {exc}',
                'repo_root': str(Path(self.repo_root)),
            }

    def _looks_like_runtime_orchestrator(self, value: object | None) -> bool:
        return value is not None and all(hasattr(value, name) for name in ('services', 'components', 'state', 'readiness'))

    def _overall_status(self, checks: list[HealthCheckView]) -> str:
        if any(item.status == 'fail' for item in checks):
            return 'fail'
        if any(item.status == 'warn' for item in checks):
            return 'warn'
        return 'pass'

    def _is_ready(self, report: dict[str, object], *, events: tuple[str, ...]) -> bool:
        if report['status'] == 'fail':
            return False
        for event in events:
            if str(event).strip().lower().startswith('error'):
                return False
        runtime_readiness = dict(report['details']).get('runtime_readiness')
        if isinstance(runtime_readiness, dict):
            return bool(runtime_readiness.get('ready', False))
        return True

    def _is_storage_ready(self, report: dict[str, object], *, events: tuple[str, ...]) -> bool:
        if not self._is_ready(report, events=events):
            return False
        runtime_readiness = dict(report['details']).get('runtime_readiness')
        if isinstance(runtime_readiness, dict):
            components = runtime_readiness.get('components')
            if isinstance(components, dict):
                return all(bool(item) for item in components.values()) if components else True
        return True

    def _is_execution_ready(self, report: dict[str, object], *, events: tuple[str, ...]) -> bool:
        if not self._is_ready(report, events=events):
            return False
        runtime_readiness = dict(report['details']).get('runtime_readiness')
        if isinstance(runtime_readiness, dict):
            services = runtime_readiness.get('services')
            if isinstance(services, dict):
                return all(bool(item) for item in services.values()) if services else True
        return True