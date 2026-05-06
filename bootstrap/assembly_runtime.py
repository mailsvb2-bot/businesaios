from __future__ import annotations
CANON_BOOT_ASSEMBLY_RUNTIME_FINAL_OWNER = True


CANON_BOOT_WIRING_ONLY = True

from typing import Any, Tuple

from runtime.events import EventLog
from runtime.tenancy import normalize_tenant_id
from runtime.platform.config.env_flags import env_str


def build_event_log_and_bindings(*, event_store: Any, decision_archive: Any):
    from runtime.tenancy import TenantScope
    from runtime.ads import bind_runtime_state

    event_log = EventLog(event_store, tenant=TenantScope.from_env())
    bind_runtime_state(event_store=event_store)
    return event_log, decision_archive


def validate_payments_webhook_prod_strict(settings: Any) -> None:
    if getattr(getattr(settings, "core", None), "env", "") != "prod":
        return
    if not bool(getattr(getattr(settings, "core", None), "production_strict_mode", False)):
        return

    prefix = "YOO" + "KASSA"
    auth_mode = env_str(prefix + "_WEBHOOK_AUTH_MODE", "token").strip().lower()
    if auth_mode == "none":
        raise RuntimeError("PROD_STRICT: " + prefix + "_WEBHOOK_AUTH_MODE=none is forbidden")
    if auth_mode == "basic":
        user = env_str(prefix + "_WEBHOOK_BASIC_USER").strip()
        password = env_str(prefix + "_WEBHOOK_BASIC_PASS").strip()
        if not (user and password):
            raise RuntimeError("PROD_STRICT: basic auth requires " + prefix + " credentials")
    if auth_mode == "token":
        token = env_str(prefix + "_WEBHOOK_TOKEN").strip()
        if not token:
            raise RuntimeError("PROD_STRICT: token auth requires " + prefix + "_WEBHOOK_TOKEN")


def resolve_tenant_and_pricing(settings: Any) -> Tuple[Any, str]:
    pricing = settings.pricing
    tenant_id = normalize_tenant_id(
        getattr(getattr(settings, "core", None), "tenant_id", "") or env_str("TENANT_ID")
    )
    if tenant_id:
        return pricing, tenant_id

    run_mode = env_str("RUN_MODE", env_str("MODE", "demo")).strip().lower()
    env_name = env_str("ENV", "dev").strip().lower()
    if run_mode == "demo" or env_name in {"dev", "local", "test"}:
        return pricing, "demo"
    return pricing, tenant_id
