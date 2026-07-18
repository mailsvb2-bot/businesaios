"""Crash-recovery worker.

RuntimeExecutor enqueues an outbox item before effect dispatch and records
terminal delivery state only through the canonical outcome-persistence owner.
This module recovers unfinished deliveries without introducing any new decision
logic or alternate execution workflow.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any

from runtime.execution.executor_commit import (
    _decision_tenant_id,
    claim_or_skip,
    get_delivery_info,
)
from runtime.execution.outcome_persistence_lock import finalize_terminal_recovery_outcome, quarantine_recovery_outcome
from runtime.executor import RuntimeExecutor
from runtime.recovery_support import DecisionArchive, log_exception_throttled

log = logging.getLogger(__name__)

CANON_RUNTIME_RECOVERY_OWNER = True
CANON_RUNTIME_RECOVERY_NO_DECISION_LOGIC = True
CANON_RUNTIME_RECOVERY_FAIL_CLOSED = True

_TERMINAL_SKIP_ACTIONS = frozenset({"skip", "noop"})
_DEAD_LETTER_ACTIONS = frozenset({"quarantine", "move_to_dead_letter", "dead_letter"})
_RESUME_ACTIONS = frozenset({"resume", "resume_delivery", "restart", "retry"})
_WAIT_ACTIONS = frozenset({"wait"})

def _recovery_plan(*, executor: RuntimeExecutor, env: Any):
    reliability = getattr(executor, "_reliability", None)
    if reliability is None:
        return None
    try:
        return reliability.plan(env)
    except Exception:
        return None

def _warn_recovery_issue(*, key: str, msg: str, exc: Exception) -> None:
    log_exception_throttled(log, key=key, msg=f"{msg} error={type(exc).__name__}", throttle_ms=60_000)

def _quarantine_item(*, outbox: Any, env: Any, item: dict[str, Any], reason: str) -> None:
    decision_id = _decision_id_from_item(item)
    if not decision_id:
        return
    quarantine_executor = SimpleNamespace(_outbox=outbox, _events=None, _reliability=None)
    quarantine_env = env
    if getattr(env, "decision", None) is None:
        quarantine_env = SimpleNamespace(
            decision=SimpleNamespace(
                decision_id=decision_id,
                action="",
                correlation_id=str(item.get("correlation_id") or decision_id),
                payload={"tenant_id": _item_tenant_id(item)},
            )
        )
    try:
        quarantine_recovery_outcome(
            executor=quarantine_executor,
            env=quarantine_env,
            reason=str(reason),
        )
    except Exception as exc:
        _warn_recovery_issue(key="recovery.dead_letter.move", msg="recovery: failed to quarantine", exc=exc)

def _normalize_item(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    if item is None:
        return {}
    return {
        "message_id": getattr(item, "message_id", ""),
        "decision_id": getattr(item, "decision_id", getattr(item, "message_id", "")),
        "tenant_id": getattr(item, "tenant_id", "default"),
        "state": getattr(getattr(item, "state", None), "value", getattr(item, "state", None)),
        "delivery_attempts": getattr(item, "delivery_attempts", None),
        "available_at": getattr(item, "available_at", None),
    }

def _iter_recoverable_items(*, outbox: Any, limit: int) -> Iterable[dict[str, Any]]:
    if outbox is None:
        return ()
    max_items = max(0, int(limit))
    if max_items == 0:
        return ()
    if hasattr(outbox, "list_claimable_all"):
        try:
            return tuple(_normalize_item(item) for item in outbox.list_claimable_all(limit=max_items))
        except Exception:
            return ()
    if hasattr(outbox, "list_claimable"):
        try:
            return tuple(_normalize_item(item) for item in outbox.list_claimable(limit=max_items))
        except TypeError:
            try:
                return tuple(_normalize_item(item) for item in outbox.list_claimable(tenant_id="default", limit=max_items))
            except Exception:
                return ()
        except Exception:
            return ()
    if hasattr(outbox, "list_pending"):
        try:
            return tuple(_normalize_item(item) for item in outbox.list_pending(limit=max_items))
        except Exception:
            return ()
    return ()

def _item_tenant_id(item: dict[str, Any]) -> str:
    tenant_id = str(item.get("tenant_id") or "default").strip()
    return tenant_id or "default"

def _decision_id_from_item(item: dict[str, Any]) -> str:
    return str(item.get("decision_id") or item.get("id") or item.get("message_id") or "").strip()

def _env_tenant_id(*, env: Any, item: dict[str, Any]) -> str:
    decision = getattr(env, "decision", None)
    if decision is not None:
        try:
            tenant_id = str(_decision_tenant_id(decision) or "").strip()
            if tenant_id:
                return tenant_id
        except Exception:
            pass
    return str(item.get("tenant_id") or "").strip()

def _resolve_recovery_tenant_id(*, env: Any, item: dict[str, Any]) -> str | None:
    tenant_id = _env_tenant_id(env=env, item=item)
    if tenant_id:
        return tenant_id
    metadata = getattr(env, "metadata", None)
    if isinstance(metadata, dict):
        nested = str(metadata.get("tenant_id") or "").strip()
        if nested:
            return nested
    return None

def _ensure_claim_or_skip(*, outbox: Any, item: dict[str, Any]) -> bool:
    decision_id = _decision_id_from_item(item)
    if not decision_id:
        return False
    tenant_id = _item_tenant_id(item)
    status_value = str(item.get("status") or item.get("state") or "").strip().lower()
    if status_value == "delivering":
        try:
            current = get_delivery_info(outbox, decision_id=decision_id, tenant_id=tenant_id)
        except Exception:
            current = None
        if isinstance(current, dict) and str(current.get("status") or current.get("state") or "").strip().lower() == "delivering":
            return True
    try:
        return bool(claim_or_skip(outbox, decision_id=decision_id, tenant_id=tenant_id, owner_id="runtime-recovery"))
    except Exception:
        return False

def _finalize_terminal_skip(*, outbox: Any, env: Any, item: dict[str, Any], reason: str) -> None:
    decision_id = _decision_id_from_item(item)
    if not decision_id:
        return
    terminal_executor = SimpleNamespace(_outbox=outbox, _events=None, _reliability=None)
    terminal_env = env
    if getattr(env, "decision", None) is None:
        terminal_env = SimpleNamespace(
            decision=SimpleNamespace(
                decision_id=decision_id,
                action="",
                correlation_id=str(item.get("correlation_id") or decision_id),
                payload={"tenant_id": _item_tenant_id(item)},
            )
        )
    try:
        finalize_terminal_recovery_outcome(
            executor=terminal_executor,
            env=terminal_env,
            reason=str(reason),
            backend_name="runtime_recovery_terminal",
        )
    except Exception as exc:
        _warn_recovery_issue(key="recovery.terminal_skip.finalize", msg="recovery: failed to finalize terminal skip", exc=exc)

def _plan_action(plan: Any) -> str:
    return str(getattr(plan, "recovery_action", "") or "").strip().lower()

def _resolve_recovery_action(*, executor: RuntimeExecutor, env: Any) -> str:
    return _plan_action(_recovery_plan(executor=executor, env=env))

def _handle_non_resume_action(*, action: str, outbox: Any, env: Any, item: dict[str, Any]) -> bool:
    _ = _decision_id_from_item(item)
    if action in _DEAD_LETTER_ACTIONS:
        _quarantine_item(outbox=outbox, env=env, item=item, reason=f"recovery_plan_{action}")
        return True
    if action in _TERMINAL_SKIP_ACTIONS:
        _finalize_terminal_skip(outbox=outbox, env=env, item=item, reason=f"recovery_plan_{action}")
        return True
    if action in _WAIT_ACTIONS:
        return True
    if action and action not in _RESUME_ACTIONS:
        _quarantine_item(outbox=outbox, env=env, item=item, reason=f"unknown_recovery_action_{action}")
        return True
    return False

def _handle_recovery_execution_failure(*, outbox: Any, env: Any, item: dict[str, Any], exc: Exception) -> None:
    decision_id = _decision_id_from_item(item)
    tenant_id = _resolve_recovery_tenant_id(env=env, item=item)
    name = type(exc).__name__
    if tenant_id is None:
        log_exception_throttled(
            log,
            key="recovery.execute_recovery.missing_tenant",
            msg=f"recovery: execute_recovery failed with unresolved tenant; quarantining decision_id={decision_id} error={name}",
            throttle_ms=10_000,
        )
        _quarantine_item(outbox=outbox, env=env, item=item, reason=f"missing_recovery_tenant:{name}")
        return
    if name in {"DecisionExpired", "DecisionInvalid", "DecisionSignatureInvalid"} or "DECISION_EXPIRED" in str(exc):
        _quarantine_item(outbox=outbox, env=env, item=item, reason=name)
        return
    log_exception_throttled(
        log,
        key="recovery.execute_recovery",
        msg=f"recovery: execute_recovery failed; quarantining decision_id={decision_id} error={name}",
        throttle_ms=10_000,
    )
    _quarantine_item(outbox=outbox, env=env, item=item, reason=name)

def recover_pending(
    *,
    executor: RuntimeExecutor,
    outbox,
    archive: DecisionArchive,
    limit: int = 100,
) -> int:
    """Recover pending effects and return the number of recovered items."""

    if outbox is None or archive is None:
        return 0

    recovered = 0
    for item in _iter_recoverable_items(outbox=outbox, limit=int(limit)):
        decision_id = _decision_id_from_item(item)
        if not decision_id:
            continue
        env = archive.get(decision_id)
        if env is None:
            _quarantine_item(outbox=outbox, env=SimpleNamespace(decision=None), item=item, reason="missing_archive_envelope")
            continue

        action = _resolve_recovery_action(executor=executor, env=env)
        if _handle_non_resume_action(action=action, outbox=outbox, env=env, item=item):
            continue
        if not _ensure_claim_or_skip(outbox=outbox, item=item):
            continue

        try:
            executor.execute_recovery(env)
            recovered += 1
        except Exception as exc:
            _handle_recovery_execution_failure(outbox=outbox, env=env, item=item, exc=exc)
    return recovered

__all__ = [
    "CANON_RUNTIME_RECOVERY_FAIL_CLOSED",
    "CANON_RUNTIME_RECOVERY_NO_DECISION_LOGIC",
    "CANON_RUNTIME_RECOVERY_OWNER",
    "recover_pending",
]
