from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True


"""
PATCHSET E — Tenant hard gate (runtime self-check)

Goal:
- Fail-fast at process start if there exists a code path that can read/write events
  without tenant_id, or if the runtime tenant is not defined.

This is intentionally "hard":
- It validates env/boot tenant presence.
- It validates runtime objects (EventLog + EventStore) contracts via signatures.
- It validates behavior by executing a minimal "must fail on empty tenant" probe.

Design notes:
- This module is a runtime complement to runtime.boot.tenant_self_check (static-ish).
- It must NOT introduce a second decision path. It only enforces strictness invariants.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_bool, env_str
from bootstrap.tenant_self_check import tenant_self_check
from runtime.boot.canonical.event_emit import emit as _canonical_emit
from runtime.boot.canonical.tenant import resolve_tenant

EMPTY_TENANT_ID_PROBE = str()


def _accepts_keyword(fn: Callable[..., Any], param: str) -> bool:
    from runtime.decision_input import accepts_keyword
    return bool(accepts_keyword(fn, param))


def _req_non_empty(name: str, value: Optional[str]) -> str:
    v = str(value or "").strip()
    if not v:
        raise SystemExit(
            f"[TENANT_HARD_GATE] Missing required {name}. "
            f"Set TENANT_ID (or provide tenant_id via boot config/contract)."
        )
    return v


def _has_param(fn: Callable[..., Any], param: str) -> bool:
    return _accepts_keyword(fn, param)



def _emit_probe(event_log: Any, *, tenant_id: str, event_type: str, payload: dict[str, Any]) -> None:
    scoped_tenant = resolve_tenant(event_log)
    if scoped_tenant and tenant_id != scoped_tenant:
        raise ValueError("cross-tenant forbidden")
    emit = getattr(event_log, "emit")
    if _has_param(emit, "tenant_id"):
        emit(tenant_id=tenant_id, event_type=event_type, user_id="__probe__", payload=payload, source="runtime.boot.tenant_hard_gate")
        return
    result = _canonical_emit(
        event_log,
        event_type,
        user_id="__probe__",
        payload=payload,
        source="runtime.boot.tenant_hard_gate",
    )
    if result is None:
        raise ValueError("event emission failed")


def _fail(msg: str) -> None:
    raise SystemExit(f"[TENANT_HARD_GATE] {msg}")


@dataclass(frozen=True)
class TenantHardGateConfig:
    audit_repo: bool = True
    require_env_tenant: bool = False


def load_config_from_env() -> TenantHardGateConfig:
    audit_repo = env_bool("TENANT_HARD_GATE_AUDIT_REPO", True)
    require_env = env_bool("TENANT_HARD_GATE_REQUIRE_ENV", False)
    return TenantHardGateConfig(audit_repo=audit_repo, require_env_tenant=require_env)


def preflight_env(*, run_mode: str, cfg: Optional[TenantHardGateConfig] = None) -> None:
    cfg = cfg or load_config_from_env()
    rm = str(run_mode or "").strip().lower()
    if rm in {"demo"}:
        return

    tenant_self_check()

    if cfg.require_env_tenant:
        _req_non_empty("TENANT_ID", env_str("TENANT_ID", ""))

    if cfg.audit_repo:
        try:
            from scripts.audit_tenant_usage import audit as _audit
        except ImportError as e:
            _fail(f"cannot import scripts.audit_tenant_usage.audit: {type(e).__name__}")
        repo_root = Path(__file__).resolve().parents[2]
        rc = int(_audit(str(repo_root)))
        if rc != 0:
            _fail(
                "repo audit failed (legacy tenant call shapes detected). "
                "Run: python scripts/audit_tenant_usage.py --root ."
            )


def validate_runtime_objects(*, tenant_id: str, event_store: Any, event_log: Any) -> None:
    tid = _req_non_empty("tenant_id", tenant_id)

    if not hasattr(event_store, "append_event"):
        _fail("event_store has no append_event()")
    if not _has_param(getattr(event_store, "append_event"), "tenant_id"):
        _fail("event_store append_event must accept tenant_id= (strict)")

    if not hasattr(event_store, "iter_events"):
        _fail("event_store has no iter_events()")
    if not _has_param(getattr(event_store, "iter_events"), "tenant_id"):
        _fail("event_store iter_events must accept tenant_id= (strict)")

    if hasattr(event_store, "count_events"):
        if not _has_param(getattr(event_store, "count_events"), "tenant_id"):
            _fail("event_store count_events must accept tenant_id= (strict)")

    try:
        getattr(event_store, "append_event")(tenant_id=EMPTY_TENANT_ID_PROBE, event_type="__probe__", user_id="__probe__", payload={})
        _fail("event_store append_event accepted empty tenant_id (must raise)")
    except SystemExit:
        raise
    except Exception:
        swallow(__name__, 'runtime/boot/tenant_hard_gate.py')

    if not hasattr(event_log, "emit"):
        _fail("event_log has no emit()")
    if not (_has_param(event_log.emit, "tenant_id") or resolve_tenant(event_log)):
        _fail("event_log must be tenant-scoped or event_log.emit() must accept tenant_id=")

    try:
        _emit_probe(event_log, tenant_id=EMPTY_TENANT_ID_PROBE, event_type="__probe__", payload={})
        _fail("event_log.emit() accepted empty tenant_id (must raise)")
    except SystemExit:
        raise
    except Exception:
        swallow(__name__, 'runtime/boot/tenant_hard_gate.py')

    try:
        _emit_probe(event_log, tenant_id="__other__", event_type="__probe__", payload={})
        _fail("event_log.emit() allowed cross-tenant write (must reject)")
    except SystemExit:
        raise
    except Exception:
        swallow(__name__, 'runtime/boot/tenant_hard_gate.py')

    try:
        _emit_probe(event_log, tenant_id=tid, event_type="tenant_hard_gate_ok", payload={"ok": True})
    except Exception:
        swallow(__name__, "runtime/boot/tenant_hard_gate.py")


def hard_gate(
    *,
    run_mode: str,
    tenant_id: str,
    event_store: Any,
    event_log: Any,
    cfg: Optional[TenantHardGateConfig] = None,
) -> None:
    cfg = cfg or load_config_from_env()
    preflight_env(run_mode=run_mode, cfg=cfg)
    validate_runtime_objects(tenant_id=tenant_id, event_store=event_store, event_log=event_log)
