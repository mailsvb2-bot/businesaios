from __future__ import annotations

import logging
from typing import Any

from bootstrap.safety_control_boot import build_safety_control_runtime

logger = logging.getLogger(__name__)


def _runtime_registry_blocks(*, action: str) -> bool:
    runtime = build_safety_control_runtime()
    return any(snapshot.active for snapshot in runtime.profile.kill_switch_registry.matching(str(action)))


def enforce_kill_switch(*, kill_switch: Any, spec: Any, tenant_id: str, user_id: str) -> None:
    action_prefix = str(getattr(spec, 'action_type', None) or getattr(spec, 'name', None) or getattr(spec, 'kind', None) or '').strip()
    if action_prefix and _runtime_registry_blocks(action=action_prefix):
        raise RuntimeError(f"KILL_SWITCHED kind={action_prefix}")
    if kill_switch is None:
        return
    try:
        kind = getattr(getattr(spec, "limits", None), "kind", None)
        if isinstance(kind, str) and kind.strip():
            kill_switch.require_allowed(kind, tenant_id=tenant_id, user_id=user_id)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning("kill_switch_check_failed", extra={"tenant_id": tenant_id, "user_id": user_id, "component": __name__, "error": exc.__class__.__name__})
