from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from pathlib import Path
from typing import Any, Callable

from bootstrap.tenant_self_check import tenant_self_check
from runtime.boot.canonical.event_emit import emit as _canonical_emit
from runtime.boot.canonical.tenant import resolve_tenant
from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_bool, env_str

CANON_BOOT_WIRING_ONLY = True
EMPTY_TENANT_ID_PROBE = str()


def _has_param(fn: Callable[..., Any], param: str) -> bool:
    from runtime.decision_input import accepts_keyword

    return bool(accepts_keyword(fn, param))


def _accepts_positional_event(fn: Callable[..., Any]) -> bool:
    try:
        signature(fn).bind({"tenant_id": EMPTY_TENANT_ID_PROBE})
    except (TypeError, ValueError):
        return False
    return True


def _req_non_empty(name: str, value: str | None) -> str:
    value = str(value or "").strip()
    if not value:
        raise SystemExit(
            f"[TENANT_HARD_GATE] Missing required {name}. Set TENANT_ID "
            "(or provide tenant_id via boot config/contract)."
        )
    return value


def _emit_probe(event_log: Any, *, tenant_id: str, event_type: str, payload: dict[str, Any]) -> None:
    scoped_tenant = resolve_tenant(event_log)
    if scoped_tenant and tenant_id != scoped_tenant:
        raise ValueError("cross-tenant forbidden")
    emit = getattr(event_log, "emit")
    if _has_param(emit, "tenant_id"):
        emit(tenant_id=tenant_id, event_type=event_type, user_id="__probe__", payload=payload, source="runtime.boot.tenant_hard_gate")
        return
    if _canonical_emit(event_log, event_type, user_id="__probe__", payload=payload, source="runtime.boot.tenant_hard_gate") is None:
        raise ValueError("event emission failed")


def _fail(msg: str) -> None:
    raise SystemExit(f"[TENANT_HARD_GATE] {msg}")


def _expect_emit_rejection(event_log: Any, *, tenant_id: str, failure: str) -> None:
    try:
        _emit_probe(event_log, tenant_id=tenant_id, event_type="__probe__", payload={})
        _fail(failure)
    except SystemExit:
        raise
    except Exception:
        swallow(__name__, "runtime/boot/tenant_hard_gate.py")


@dataclass(frozen=True)
class TenantHardGateConfig:
    audit_repo: bool = True
    require_env_tenant: bool = False


def load_config_from_env() -> TenantHardGateConfig:
    return TenantHardGateConfig(
        audit_repo=env_bool("TENANT_HARD_GATE_AUDIT_REPO", True),
        require_env_tenant=env_bool("TENANT_HARD_GATE_REQUIRE_ENV", False),
    )


def preflight_env(*, run_mode: str, cfg: TenantHardGateConfig | None = None) -> None:
    cfg = cfg or load_config_from_env()
    if str(run_mode or "").strip().lower() == "demo":
        return
    tenant_self_check()
    if cfg.require_env_tenant:
        _req_non_empty("TENANT_ID", env_str("TENANT_ID", ""))
    if not cfg.audit_repo:
        return
    try:
        from scripts.audit_tenant_usage import audit
    except ImportError as exc:
        _fail(f"cannot import scripts.audit_tenant_usage.audit: {type(exc).__name__}")
    if int(audit(str(Path(__file__).resolve().parents[1]))) != 0:
        _fail("repo audit failed (legacy tenant call shapes detected). Run: python scripts/audit_tenant_usage.py --root .")


def validate_runtime_objects(*, tenant_id: str, event_store: Any, event_log: Any) -> None:
    tenant_id = _req_non_empty("tenant_id", tenant_id)
    append_event = getattr(event_store, "append_event", None)
    if not callable(append_event):
        _fail("event_store has no append_event()")
    accepts_tenant = _has_param(append_event, "tenant_id")
    accepts_event = _has_param(append_event, "event") and _accepts_positional_event(append_event)
    if not (accepts_tenant or accepts_event):
        _fail("event_store append_event must accept tenant_id= or exactly one positional strict event payload")

    iter_events = getattr(event_store, "iter_events", None)
    if not callable(iter_events):
        _fail("event_store has no iter_events()")
    if not _has_param(iter_events, "tenant_id"):
        _fail("event_store iter_events must accept tenant_id= (strict)")
    count_events = getattr(event_store, "count_events", None)
    if count_events is not None and not _has_param(count_events, "tenant_id"):
        _fail("event_store count_events must accept tenant_id= (strict)")

    probe = {"tenant_id": EMPTY_TENANT_ID_PROBE, "event_type": "__probe__", "user_id": "__probe__", "payload": {}}
    try:
        append_event(**probe) if accepts_tenant else append_event(probe)
        _fail("event_store append_event accepted empty tenant_id (must raise)")
    except SystemExit:
        raise
    except TypeError as exc:
        _fail(f"event_store append_event contract is unusable: {exc}")
    except Exception:
        swallow(__name__, "runtime/boot/tenant_hard_gate.py")

    emit = getattr(event_log, "emit", None)
    if not callable(emit):
        _fail("event_log has no emit()")
    if not (_has_param(emit, "tenant_id") or resolve_tenant(event_log)):
        _fail("event_log must be tenant-scoped or event_log.emit() must accept tenant_id=")
    _expect_emit_rejection(event_log, tenant_id=EMPTY_TENANT_ID_PROBE, failure="event_log.emit() accepted empty tenant_id (must raise)")
    _expect_emit_rejection(event_log, tenant_id="__other__", failure="event_log.emit() allowed cross-tenant write (must reject)")
    try:
        _emit_probe(event_log, tenant_id=tenant_id, event_type="tenant_hard_gate_ok", payload={"ok": True})
    except Exception:
        swallow(__name__, "runtime/boot/tenant_hard_gate.py")


def hard_gate(*, run_mode: str, tenant_id: str, event_store: Any, event_log: Any, cfg: TenantHardGateConfig | None = None) -> None:
    cfg = cfg or load_config_from_env()
    preflight_env(run_mode=run_mode, cfg=cfg)
    validate_runtime_objects(tenant_id=tenant_id, event_store=event_store, event_log=event_log)
