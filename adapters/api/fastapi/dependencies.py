from __future__ import annotations

"""Final owner: adapters.api.fastapi.dependencies."""

CANON_FASTAPI_DEPENDENCIES_FINAL_OWNER = True
CANON_FASTAPI_DEPENDENCIES_BOOT_RESULT_ONLY = True


from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
import os

from boot.app_boot_result import AppBootResult
from boot.bootstrap_config_surface import BootstrapConfigSurface, build_bootstrap_config_surface
from application.decision.decision_service import DecisionApplicationService
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from observability.action_audit_log import ActionAuditLog, build_default_action_audit_log
from observability.audit_export_service import AuditExportService
from observability.decision_audit_log import DecisionAuditLog, build_default_decision_audit_log
from observability.metrics import InMemoryMetrics
from observability.platform.telemetry.event_store import build_default_event_store
from reliability.idempotency_scope import build_idempotency_key
from reliability.idempotency_sqlite_backend import SQLiteIdempotencyStore
from security.audit_redaction_policy import AuditRedactionPolicy
from security.key_provider import KeyProvider, build_default_key_provider, describe_key_provider_backend, key_provider_sqlite_path
from security.payload_redaction import PayloadRedactor
from security.secret_vault import SecretVault, build_default_secret_vault, secret_vault_sqlite_path
from security.key_rotation_scheduler import KeyRotationScheduler, KeyRotationSchedulerConfig, StdlibSecretReencryptionAdapter
from security.key_provider_sqlite import SqliteKeyProviderBackend
from security.secret_vault_sqlite import SqliteSecretVaultBackend
from security.session_policy import SessionPolicy
from security.token_policy import TokenPolicy
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, build_default_tenant_policy_store
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_registry import InMemoryTenantRegistry, build_default_tenant_registry


def _resolve_runtime_infra(boot_result: AppBootResult):
    runtime = getattr(boot_result, 'runtime', None)
    for candidate in (
        getattr(boot_result, 'runtime_infra', None),
        getattr(runtime, 'runtime_infra', None),
        getattr(getattr(runtime, 'exports', None), 'runtime_infra', None),
        getattr(getattr(boot_result, 'decision_application', None), 'runtime_infra', None),
    ):
        if candidate is not None:
            return candidate
    return None


def _resolve_tenant_runtime_service(boot_result: AppBootResult, attr_name: str, default_factory):
    runtime_infra = _resolve_runtime_infra(boot_result)
    candidate = getattr(runtime_infra, attr_name, None) if runtime_infra is not None else None
    return candidate if candidate is not None else default_factory()


@dataclass(frozen=True)
class FastAPIBootResult:
    """Explicit FastAPI boot-result projection.

    Keeps API dependency wiring from depending on a giant runtime object while
    preserving the canonical fields used by readiness, control-plane and audit
    surfaces.
    """

    decision_application: object
    runtime: object
    runtime_infra: object | None = None
    startup_report: tuple[str, ...] = ()

@dataclass(frozen=True)
class FastAPIDependencyContainer:
    boot_result: AppBootResult
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    audit_redaction_policy: AuditRedactionPolicy = field(default_factory=AuditRedactionPolicy)
    session_policy: SessionPolicy = field(default_factory=SessionPolicy)
    token_policy: TokenPolicy = field(default_factory=TokenPolicy)
    key_provider: KeyProvider = field(default_factory=build_default_key_provider)
    secret_vault: SecretVault = field(default_factory=build_default_secret_vault)
    tenant_registry: InMemoryTenantRegistry | object | None = None
    tenant_policy_store: InMemoryTenantPolicyStore | object | None = None
    tenant_quota_guard: TenantQuotaGuard | object | None = None
    api_idempotency_store: SQLiteIdempotencyStore | None = None
    config_surface: BootstrapConfigSurface | None = None
    shared_observability: Mapping[str, object] | None = None
    api_idempotency_namespace: str = 'api_request'
    api_idempotency_operation: str = 'execute_action'
    api_idempotency_owner_id: str = 'fastapi-dependency-container'
    _api_security_owner_bundle: ApiSecurityOwnerBundle | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.config_surface is None:
            object.__setattr__(self, "config_surface", build_bootstrap_config_surface())
        if self.shared_observability is None:
            object.__setattr__(self, 'shared_observability', {})
        if self.tenant_registry is None:
            object.__setattr__(self, 'tenant_registry', _resolve_tenant_runtime_service(self.boot_result, 'tenant_registry', build_default_tenant_registry))
        if self.tenant_policy_store is None:
            object.__setattr__(self, 'tenant_policy_store', _resolve_tenant_runtime_service(self.boot_result, 'tenant_policy_store', build_default_tenant_policy_store))
        if self.tenant_quota_guard is None:
            quota_candidate = _resolve_runtime_infra(self.boot_result)
            quota_guard = getattr(quota_candidate, 'tenant_quota_guard', None) if quota_candidate is not None else None
            if quota_guard is None:
                quota_guard = TenantQuotaGuard(policy_store=self.tenant_policy_store)
            object.__setattr__(self, 'tenant_quota_guard', quota_guard)
        if self.api_idempotency_store is None:
            object.__setattr__(self, 'api_idempotency_store', SQLiteIdempotencyStore(self._default_api_idempotency_path()))

    def application_service(self) -> DecisionApplicationService:
        return self.boot_result.decision_application

    def startup_events(self) -> tuple[str, ...]:
        report = getattr(self.boot_result, 'startup_report', ()) or ()
        return tuple(str(item) for item in report)

    def request_context(
        self,
        headers: Mapping[str, Any] | None = None,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> RequestContext:
        return RequestContext.from_headers(headers, metadata=metadata)

    def tenant_context(
        self,
        headers: Mapping[str, Any] | None = None,
        *,
        metadata: Mapping[str, Any] | None = None,
        required: bool = False,
    ):
        return self.request_context(headers, metadata=metadata).tenant_context(required=required)

    def key_material(self, key_id: str):
        return self.key_provider.get(key_id)

    def secret_plaintext(self, ref):
        return self.secret_vault.get(ref)

    def security_storage_diagnostics(self) -> dict[str, Any]:
        key_backend = describe_key_provider_backend()
        secret_backend = str(os.getenv('BUSINESAIOS_SECRET_VAULT_BACKEND', 'file')).strip().lower() or 'file'
        actual_key_provider = self.key_provider.__class__.__name__
        actual_secret_vault = self.secret_vault.__class__.__name__
        shared_runtime_storage = key_backend == 'sqlite' and secret_backend == 'sqlite'
        key_provider_sqlite = actual_key_provider == 'SqliteKeyProvider'
        secret_vault_sqlite = actual_secret_vault == 'SqliteSecretVault'
        return {
            'key_provider_backend': key_backend,
            'secret_vault_backend': secret_backend,
            'shared_runtime_storage': shared_runtime_storage and key_provider_sqlite and secret_vault_sqlite,
            'actual_key_provider_class': actual_key_provider,
            'actual_secret_vault_class': actual_secret_vault,
        }

    def key_rotation_scheduler(self) -> KeyRotationScheduler:
        diagnostics = self.security_storage_diagnostics()
        if diagnostics['shared_runtime_storage'] is not True:
            raise RuntimeError('key_rotation_scheduler requires sqlite key_provider and sqlite secret_vault backends')
        key_backend = SqliteKeyProviderBackend(key_provider_sqlite_path())
        secret_backend = SqliteSecretVaultBackend(secret_vault_sqlite_path())
        return KeyRotationScheduler(
            key_backend=key_backend,
            secret_backend=secret_backend,
            secret_reencryption_adapter=StdlibSecretReencryptionAdapter(key_provider=self.key_provider),
            config=KeyRotationSchedulerConfig(),
        )

    def _shared(self, key: str) -> object | None:
        return self.shared_observability.get(key) if isinstance(self.shared_observability, Mapping) else None

    def action_audit_log(self) -> ActionAuditLog:
        shared = self._shared('action_audit_log')
        if isinstance(shared, ActionAuditLog):
            return shared
        runtime_infra = _resolve_runtime_infra(self.boot_result)
        candidate = getattr(runtime_infra, 'action_audit_log', None) if runtime_infra is not None else None
        if isinstance(candidate, ActionAuditLog):
            return candidate
        return build_default_action_audit_log(config_surface=self.config_surface)

    def decision_audit_log(self) -> DecisionAuditLog:
        shared = self._shared('decision_audit_log')
        if isinstance(shared, DecisionAuditLog):
            return shared
        runtime_infra = _resolve_runtime_infra(self.boot_result)
        candidate = getattr(runtime_infra, 'decision_audit_log', None) if runtime_infra is not None else None
        if isinstance(candidate, DecisionAuditLog):
            return candidate
        return build_default_decision_audit_log(config_surface=self.config_surface)

    def audit_export_service(self) -> AuditExportService:
        shared = self._shared('audit_export_service')
        if isinstance(shared, AuditExportService):
            return shared
        return AuditExportService(config_surface=self.config_surface)


    def telemetry_event_store(self):
        shared = self._shared('telemetry_event_store')
        if shared is not None:
            return shared
        return build_default_event_store(config_surface=self.config_surface)

    def metrics(self) -> InMemoryMetrics:
        shared = self._shared('metrics')
        if isinstance(shared, InMemoryMetrics):
            return shared
        runtime = getattr(self.boot_result, 'runtime', None)
        metrics = getattr(runtime, 'metrics', None)
        if isinstance(metrics, InMemoryMetrics):
            return metrics
        return InMemoryMetrics()

    def redact_payload(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        redacted = self.payload_redactor.redact(dict(payload or {}))
        if isinstance(redacted, dict):
            return redacted
        return {'payload': redacted}

    def redact_audit_event(self, event: Mapping[str, Any] | None) -> dict[str, Any]:
        return self.audit_redaction_policy.redact_event_dict(dict(event or {}))

    def security_owner_bundle(self) -> ApiSecurityOwnerBundle:
        cached = self._api_security_owner_bundle
        if cached is not None:
            return cached
        shared = self._shared('api_security_owner_bundle')
        if isinstance(shared, ApiSecurityOwnerBundle):
            object.__setattr__(self, '_api_security_owner_bundle', shared)
            return shared
        runtime_infra = _resolve_runtime_infra(self.boot_result)
        candidate = getattr(runtime_infra, 'api_security_owner_bundle', None) if runtime_infra is not None else None
        if isinstance(candidate, ApiSecurityOwnerBundle):
            object.__setattr__(self, '_api_security_owner_bundle', candidate)
            return candidate
        bundle = ApiSecurityOwnerBundle.default(audit_path=self._default_api_security_audit_path())
        object.__setattr__(self, '_api_security_owner_bundle', bundle)
        return bundle

    def _default_api_security_audit_path(self) -> Path:
        return self.config_surface.data_dir / 'security' / 'api_owner_security_audit.jsonl'


    def analytics_snapshot_db_path(self) -> Path:
        return self.config_surface.observability_data_dir / 'analytics_snapshots.sqlite3'

    def analytics_manifest_chain_db_path(self) -> Path:
        return self.config_surface.observability_data_dir / 'analytics_manifest_chain.sqlite3'

    def analytics_export_root(self) -> Path:
        return self.config_surface.observability_export_dir / 'analytics'

    def build_api_idempotency_key(
        self,
        *,
        tenant_id: str,
        request_id: str,
        payload: Mapping[str, Any] | None = None,
        operation: str | None = None,
    ):
        return build_idempotency_key(
            tenant_id=tenant_id,
            namespace=self.api_idempotency_namespace,
            operation=str(operation or self.api_idempotency_operation),
            key=str(request_id),
            semantic_scope={
                'payload': dict(payload or {}),
                'request_id': str(request_id),
            },
        )

    def config_snapshot(self) -> dict[str, str]:
        return self.config_surface.snapshot()

    def _default_api_idempotency_path(self) -> Path:
        return self.config_surface.api_idempotency_path
