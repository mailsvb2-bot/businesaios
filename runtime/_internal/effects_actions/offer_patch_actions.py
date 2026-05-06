from __future__ import annotations
"""Sealed effect actions mixin.

This module is INTERNAL to runtime/_internal.
No API changes to EffectsPort.
"""

from typing import Any, Dict

from runtime.security.runtime_asserts import assert_called_from_executor

from runtime.observability.error_handling import swallow
from runtime.platform.config.yaml_loader import load_yaml
from runtime._internal.effects_actions.offer_patch_apply_support import (
    load_offer_catalog,
    locate_offer,
    resolve_offer_catalog,
    suggest_patch_for_action,
    summarize_patch_application,
)


class OfferPatchEffectsMixin:
    def suggest_offer_patch(
        self,
        *,
        tenant_id: str,
        product: str,
        env: str,
        offer_id: str,
        action: str,
        notify_user_id: str | None = None,
        callback_query_id: str | None = None,
    ) -> Dict[str, Any]:
        assert_called_from_executor()
        scope, cat_path = resolve_offer_catalog(tenant_id=tenant_id, product=product, env=env)
        spec = load_offer_catalog(cat_path)
        offers = spec.get("offers") if isinstance(spec.get("offers"), list) else []
        target = locate_offer(offers=offers, offer_id=offer_id)
        title, reason, patch = suggest_patch_for_action(target=target, action=action)
        out = {"ok": True, "offer_id": str(offer_id).strip() or "unknown_offer", "action": str(action).strip() or "improve_ctr", "title": title, "reason": reason, "patch": patch}
        if notify_user_id:
            did = f"suggest_offer_patch:{scope}:{str(offer_id).strip() or 'unknown_offer'}:{str(action).strip() or 'improve_ctr'}"
            self.send_message(
                decision_id=did,
                correlation_id=did,
                user_id=str(notify_user_id),
                text=(
                    f"🧩 Suggest offer patch\n"
                    f"Оффер: {out['offer_id']}\n"
                    f"Цель: {title}\n"
                    f"Причина: {reason}\n\n"
                    f"PATCH:\n{patch}"
                ),
                reply_markup=None,
                callback_query_id=callback_query_id,
                channel="telegram",
                priority="normal",
                critical=False,
            )
        return out

    def apply_offer_patch(
        self,
        *,
        tenant_id: str,
        product: str,
        env: str,
        offer_id: str,
        patch: Dict[str, Any],
        mode: str = "dry_run",
        notify_user_id: str | None = None,
        callback_query_id: str | None = None,
    ) -> Dict[str, Any]:
        assert_called_from_executor()
        scope, cat_path = resolve_offer_catalog(tenant_id=tenant_id, product=product, env=env)
        bak_path = cat_path.with_suffix(cat_path.suffix + ".bak")
        oid = str(offer_id).strip() or "unknown_offer"
        did = f"apply_offer_patch:{scope}:{oid}:{str(mode)}"

        if mode == "rollback":
            if not bak_path.exists():
                out = {"status": "no_backup", "path": str(cat_path)}
                if notify_user_id:
                    self.send_message(decision_id=did, correlation_id=did, user_id=str(notify_user_id), text=f"ℹ️ Нет backup для rollback: {cat_path}", reply_markup=None, callback_query_id=callback_query_id, channel="telegram", priority="normal", critical=False)
                return out
            cat_path.write_text(bak_path.read_text(encoding="utf-8"), encoding="utf-8")
            out = {"status": "rolled_back", "path": str(cat_path)}
            if notify_user_id:
                self.send_message(decision_id=did, correlation_id=did, user_id=str(notify_user_id), text=f"✅ Rollback выполнен: {cat_path}", reply_markup=None, callback_query_id=callback_query_id, channel="telegram", priority="normal", critical=False)
            return out

        raw = load_offer_catalog(cat_path)
        offers = raw.get("offers") if isinstance(raw.get("offers"), list) else []
        target = locate_offer(offers=offers, offer_id=oid)
        before, after, changed = summarize_patch_application(target=target, patch=patch if isinstance(patch, dict) else {})
        summary = {"status": "ok", "mode": str(mode), "path": str(cat_path), "offer_id": oid, "changed": changed}

        if mode == "apply":
            try:
                if cat_path.exists():
                    bak_path.write_text(cat_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                swallow(__name__, "runtime/_internal/_effects_impl.py")
            raw["offers"] = offers
            cat_path.parent.mkdir(parents=True, exist_ok=True)
            cat_path.write_text(__import__("yaml").safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
            summary["status"] = "applied"

        if notify_user_id:
            msg = "🧩 Patch preview" if mode == "dry_run" else ("✅ Patch applied" if mode == "apply" else "ℹ️ Patch")
            msg += f"\nОффер: {oid}\nChanged: {changed}\nMode: {mode}"
            self.send_message(decision_id=did, correlation_id=did, user_id=str(notify_user_id), text=msg, reply_markup=None, callback_query_id=callback_query_id, channel="telegram", priority="normal", critical=False)
        return summary
