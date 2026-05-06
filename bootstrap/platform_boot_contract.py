from __future__ import annotations

"""Final owner for platform boot contract."""

from dataclasses import dataclass

from bootstrap.bootstrap_config_surface import BootstrapConfigSurface
from bootstrap.platform_boot_surface import PlatformBootSurface, build_platform_boot_surface

CANON_PLATFORM_BOOT_CONTRACT_FINAL_OWNER = True
CANON_PLATFORM_BOOT_CONTRACT = True
CANON_PLATFORM_BOOT_CONTRACT_INTERNAL_SUPPORT = True
CANON_PLATFORM_BOOT_CONTRACT_NO_PUBLIC_ENTRYPOINT = True


@dataclass(frozen=True)
class PlatformBootIntegrityReport:
    config_shared: bool
    action_audit_shared: bool
    decision_audit_shared: bool
    export_service_shared: bool
    tenant_metrics_shared: bool
    telemetry_event_store_shared: bool
    api_security_owner_bundle_shared: bool

    @property
    def is_valid(self) -> bool:
        return all((
            self.config_shared,
            self.action_audit_shared,
            self.decision_audit_shared,
            self.export_service_shared,
            self.tenant_metrics_shared,
            self.telemetry_event_store_shared,
            self.api_security_owner_bundle_shared,
        ))

    def snapshot(self) -> dict[str, bool]:
        return {
            "config_shared": self.config_shared,
            "action_audit_shared": self.action_audit_shared,
            "decision_audit_shared": self.decision_audit_shared,
            "export_service_shared": self.export_service_shared,
            "tenant_metrics_shared": self.tenant_metrics_shared,
            "telemetry_event_store_shared": self.telemetry_event_store_shared,
            "api_security_owner_bundle_shared": self.api_security_owner_bundle_shared,
            "is_valid": self.is_valid,
        }


def validate_platform_boot_surface(surface: PlatformBootSurface) -> PlatformBootIntegrityReport:
    runtime_services = surface.runtime_surface.orchestrator.services
    runtime_components = surface.runtime_surface.orchestrator.components
    container = surface.dependency_container
    shared_payload = surface.runtime_surface.shared_observability_payload()
    return PlatformBootIntegrityReport(
        config_shared=(surface.config_surface is surface.system_surface.config_surface is surface.runtime_surface.config_surface),
        action_audit_shared=(container.action_audit_log() is runtime_components.get("action_audit_log")),
        decision_audit_shared=(container.decision_audit_log() is runtime_components.get("decision_audit_log")),
        export_service_shared=(container.audit_export_service() is runtime_services.get("audit_export_service")),
        tenant_metrics_shared=(shared_payload.get("tenant_metrics_registry") is runtime_services.get("tenant_metrics_registry")),
        telemetry_event_store_shared=(container.telemetry_event_store() is runtime_services.get("telemetry_event_store")),
        api_security_owner_bundle_shared=(container.security_owner_bundle() is surface.runtime_surface.security_surface.api_security_owner_bundle),
    )


def assert_valid_platform_boot_surface(surface: PlatformBootSurface) -> PlatformBootSurface:
    report = validate_platform_boot_surface(surface)
    if report.is_valid is not True:
        raise RuntimeError(f"platform boot integrity violation: {report.snapshot()}")
    return surface


def build_validated_platform_boot_surface(*, config_surface: BootstrapConfigSurface | None = None) -> PlatformBootSurface:
    return assert_valid_platform_boot_surface(build_platform_boot_surface(config_surface=config_surface))


__all__ = [
    "CANON_PLATFORM_BOOT_CONTRACT_FINAL_OWNER",
    "PlatformBootIntegrityReport",
    "validate_platform_boot_surface",
    "assert_valid_platform_boot_surface",
    "build_validated_platform_boot_surface",
]
