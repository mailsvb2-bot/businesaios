from __future__ import annotations

from typing import Any, Dict

from core.admin.ai_marketing import generate_copy_variants
from core.tenancy.normalization import normalize_tenant_id_or_unknown
from config.env_flags import env_path, env_str


def regenerate_marketing_copy(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministically regenerate marketing copy variants and persist as events.

    This is an EVOLUTION-timescale action:
    - No Telegram side-effects.
    - Writes only to the event store (append-only).

    Expected payload:
      - step_key: str (required)
      - admin_id: str (optional, used as user_id for audit)

    Storage wiring:
      - Uses EVENTS_DB_PATH / DATA_DIR env (legacy-compatible).
      - Uses tenant_id from TENANT_ID env (falls back to 'default').
    """

    step_key = str((payload or {}).get("step_key") or "").strip()
    if not step_key:
        raise ValueError("MISSING_STEP_KEY")

    admin_id = str((payload or {}).get("admin_id") or "system")

    vv = generate_copy_variants(step_key=step_key)

    # Append a domain event to the durable store.
    events_path = str(env_path("EVENTS_DB_PATH", "")).strip()
    if not events_path:
        data_dir = env_path("DATA_DIR", "runtime/entrypoints/data")
        events_path = str(data_dir / "events.db")

    tenant_id = normalize_tenant_id_or_unknown(env_str("TENANT_ID", ""))

    # Lazy import to avoid core->platform import edge on module load.
    from importlib import import_module

    SqliteEventStore = getattr(import_module("runtime.platform.event_store.sqlite_event_store"), "SqliteEventStore")

    with SqliteEventStore(events_path) as store:
        store.emit(
            tenant_id=tenant_id,
            event_type="marketing_copy_regenerated",
            user_id=admin_id,
            payload={
                "step_key": step_key,
                "variant_a": vv.get("a"),
                "variant_b": vv.get("b"),
            },
        )

    return {"ok": True, "step_key": step_key, "a": vv.get("a"), "b": vv.get("b")}
