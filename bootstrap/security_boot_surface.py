from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from bootstrap.bootstrap_config_surface import BootstrapConfigSurface, build_bootstrap_config_surface
from bootstrap.boot_phases import boot_phase_20_keyring
from application.decisioning.authenticated_command import AuthenticatedDecisionCommandBinding
from runtime.platform.config.env_flags import env_str

if TYPE_CHECKING:
    from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle

CANON_SECURITY_BOOT_SURFACE_FINAL_OWNER = True
CANON_SECURITY_BOOT_SURFACE = True
CANON_SECURITY_BOOT_SURFACE_INTERNAL_SUPPORT = True
CANON_SECURITY_BOOT_SURFACE_NO_PUBLIC_ENTRYPOINT = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"


@dataclass(frozen=True)
class SecurityBootSurface:
    config_surface: BootstrapConfigSurface
    api_security_owner_bundle: 'ApiSecurityOwnerBundle'
    audit_path: Path
    authenticated_command_binding: AuthenticatedDecisionCommandBinding

    def shared_runtime_payload(self) -> dict[str, object]:
        return {
            'api_security_owner_bundle': self.api_security_owner_bundle,
            'authenticated_decision_command_binding': self.authenticated_command_binding,
        }

    def snapshot(self) -> dict[str, object]:
        return {
            'audit_path': str(self.audit_path),
            'config': self.config_surface.snapshot(),
            'api_security_owner_bundle_type': type(self.api_security_owner_bundle).__name__,
            'authenticated_command_binding_type': type(self.authenticated_command_binding).__name__,
        }


def build_security_boot_surface(
    *,
    config_surface: BootstrapConfigSurface | None = None,
    audit_path: str | Path | None = None,
) -> SecurityBootSurface:
    from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle

    resolved_config_surface = config_surface or build_bootstrap_config_surface()
    resolved_audit_path = Path(audit_path) if audit_path is not None else resolved_config_surface.data_dir / 'security' / 'process_owner_security_audit.jsonl'
    bundle = ApiSecurityOwnerBundle.default(audit_path=resolved_audit_path)
    env_name = env_str('APP_ENV', env_str('ENV', 'dev')).strip().lower() or 'dev'
    command_binding = AuthenticatedDecisionCommandBinding(
        keyring=boot_phase_20_keyring(env_name)
    )
    return SecurityBootSurface(
        config_surface=resolved_config_surface,
        api_security_owner_bundle=bundle,
        audit_path=resolved_audit_path,
        authenticated_command_binding=command_binding,
    )
