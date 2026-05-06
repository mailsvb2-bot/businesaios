from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True


import inspect

from runtime.tenancy import TenantScope
from runtime.boot.env import env_bool, env_str


def _parameters(fn):
    from runtime.decision_input import parameters
    return parameters(fn)


def tenant_self_check() -> None:
    """Static-ish boot self-check for tenant strictness.

    Purpose:
      - Prevent regressions where tenant_id silently defaults again
      - Ensure core contracts require tenant_id in critical I/O paths
    """

    env = env_str("APP_ENV", env_str("ENV", "dev")).strip().lower()
    strict = env_bool("PRODUCTION_STRICT_TENANT", False)
    tid = env_str("TENANT_ID", "").strip()
    if env in {"prod", "production"} and strict:
        if not tid:
            raise RuntimeError("PROD_REQUIRES_TENANT_ID")
        if tid.strip().lower() in {"default", "legacy"}:
            raise RuntimeError(f"PROD_FORBIDS_TENANT_ID:{tid}")

    from runtime.events import EventLog

    sig = {param.name: param for param in _parameters(EventLog.__init__)}
    if "tenant" not in sig:
        raise RuntimeError("TENANT_SELF_CHECK_FAILED: EventLog.__init__ must require tenant=...")

    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    for meth in ("iter_events", "count_events"):
        ps = {param.name: param for param in _parameters(getattr(SqliteEventStore, meth))}
        if "tenant_id" not in ps:
            raise RuntimeError(f"TENANT_SELF_CHECK_FAILED: SqliteEventStore.{meth} missing tenant_id")
        if ps["tenant_id"].default is not inspect._empty:
            raise RuntimeError(f"TENANT_SELF_CHECK_FAILED: SqliteEventStore.{meth} tenant_id must be required")

    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    for meth in ("iter_events", "count_events"):
        if not hasattr(MemoryEventStore, meth):
            continue
        ps = {param.name: param for param in _parameters(getattr(MemoryEventStore, meth))}
        if "tenant_id" not in ps:
            raise RuntimeError(f"TENANT_SELF_CHECK_FAILED: MemoryEventStore.{meth} missing tenant_id")
        if ps["tenant_id"].default is not inspect._empty:
            raise RuntimeError(f"TENANT_SELF_CHECK_FAILED: MemoryEventStore.{meth} tenant_id must be required")

    try:
        TenantScope("")
        raise RuntimeError("TENANT_SELF_CHECK_FAILED: TenantScope must reject empty tenant_id")
    except ValueError:
        pass
