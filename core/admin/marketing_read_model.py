from __future__ import annotations

"""Marketing read-models (event-sourced).

Purpose:
- Provide deterministic variants for concrete UX steps (step_key).
- Keep selection inside the single DecisionCore path.

Selection itself happens in policy (deterministic hash).
The chosen variant is logged via send_message@v1 track_event_type.
"""

from typing import Any, Dict

from core.read_model.cache import global_cache, watermark_for

DEFAULTS: dict[str, dict[str, str]] = {
    "menu_main": {
        "a": "BusinesAIOS Workspace: переобучение нервной системы через ритм повседневности.\n\nГлавное меню — выбери, что сейчас нужно:",
        "b": "BusinesAIOS Workspace — мягкая практика через повседневный ритм.\n\nВыбери шаг в меню:",
    },
    "tariffs_viewed": {
        "a": "💳 Тарифы\n\nВыбери тариф:",
        "b": "💳 Доступ\n\nВыбери вариант, который подходит по ритму:",
    },
}


def marketing_variants(event_store: Any, *, tenant_id: str = "default") -> dict[str, dict[str, str]]:
    """Return latest configured variants per step_key."""
    wm = watermark_for(event_store, tenant_id=str(tenant_id), user_id=None, event_types=("marketing_copy_set",))

    def _compute() -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {k: dict(v) for k, v in DEFAULTS.items()}
        if event_store is None or not hasattr(event_store, "iter_events"):
            return out
        # We rely on DB ordering; iterate and keep last value.
        try:
            for ev in event_store.iter_events(tenant_id=str(tenant_id), start_ms=0, end_ms=None, event_type="marketing_copy_set"):
                p = ev.get("payload") or {}
                if not isinstance(p, dict):
                    continue
                step = str(p.get("step_key") or "").strip()
                if not step:
                    continue
                a = str(p.get("variant_a") or "").strip()
                b = str(p.get("variant_b") or "").strip()
                if a or b:
                    out[step] = {"a": a or out.get(step, {}).get("a", ""), "b": b or out.get(step, {}).get("b", "")}
        except Exception:
            return out
        return out

    return global_cache().get(key=("marketing_variants",), compute=_compute, watermark_ms=wm)
