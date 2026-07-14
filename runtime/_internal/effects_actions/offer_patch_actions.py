"""Governed offer-catalog preview, apply, and rollback effects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config.yaml_loader_shared import invalidate_yaml_cache
from runtime._internal.effects_actions.offer_patch_apply_support import (
    load_offer_catalog,
    locate_offer,
    resolve_offer_catalog,
    suggest_patch_for_action,
    summarize_patch_application,
)
from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.security.runtime_asserts import assert_called_from_executor


def _event_id(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("event_id") or "").strip()
    return str(getattr(event, "event_id", "") or "").strip()


def _read_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _restore_bytes(path: Path, raw: bytes | None) -> None:
    if raw is None:
        path.unlink(missing_ok=True)
        invalidate_yaml_cache(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".restore.tmp")
    temp.write_bytes(raw)
    temp.replace(path)
    invalidate_yaml_cache(path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".write.tmp")
    temp.write_text(str(text), encoding="utf-8")
    temp.replace(path)
    invalidate_yaml_cache(path)


def _ledger_evidence(
    *,
    code: str,
    event: Any,
    fallback_ref: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": str(code),
        "external_refs": [_event_id(event) or str(fallback_ref)],
        "confidence": 1.0,
        "payload": dict(payload),
    }


def _notify(
    owner: Any,
    *,
    decision_id: str,
    correlation_id: str,
    tenant_id: str,
    user_id: str | None,
    text: str,
    callback_query_id: str | None,
) -> Any:
    if not user_id:
        return None
    return owner.send_message(
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        text=str(text)[:3500],
        reply_markup=None,
        callback_query_id=callback_query_id,
        channel="telegram",
        priority="normal",
        critical=False,
    )


class OfferPatchEffectsMixin:
    def suggest_offer_patch(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        product: str,
        env: str,
        offer_id: str,
        action: str,
        notify_user_id: str | None = None,
        callback_query_id: str | None = None,
    ) -> dict[str, Any]:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="suggest_offer_patch",
        )
        scope, catalog_path = resolve_offer_catalog(
            tenant_id=tenant,
            product=product,
            env=env,
        )
        spec = load_offer_catalog(catalog_path)
        offers = spec.get("offers") if isinstance(spec.get("offers"), list) else []
        target = locate_offer(offers=offers, offer_id=offer_id)
        title, reason, patch = suggest_patch_for_action(target=target, action=action)
        result = {
            "ok": True,
            "status": "advisory",
            "tenant_id": tenant,
            "scope": scope,
            "offer_id": str(offer_id).strip(),
            "action": str(action).strip(),
            "title": title,
            "reason": reason,
            "patch": patch,
        }
        result["notification"] = _notify(
            self,
            decision_id=decision_id,
            correlation_id=correlation_id,
            tenant_id=tenant,
            user_id=notify_user_id,
            text=(
                "🧩 Suggest offer patch\n"
                f"Оффер: {result['offer_id']}\n"
                f"Цель: {title}\n"
                f"Причина: {reason}\n\n"
                f"PATCH:\n{patch}"
            ),
            callback_query_id=callback_query_id,
        )
        return result

    def apply_offer_patch(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        product: str,
        env: str,
        offer_id: str,
        patch: dict[str, Any],
        mode: str = "dry_run",
        notify_user_id: str | None = None,
        callback_query_id: str | None = None,
    ) -> dict[str, Any]:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="apply_offer_patch",
        )
        normalized_mode = str(mode or "dry_run").strip().casefold()
        if normalized_mode not in {"dry_run", "apply", "rollback"}:
            raise ValueError("INVALID_OFFER_PATCH_MODE")

        scope, catalog_path = resolve_offer_catalog(
            tenant_id=tenant,
            product=product,
            env=env,
        )
        catalog_path = Path(catalog_path)
        backup_path = catalog_path.with_suffix(catalog_path.suffix + ".bak")
        offer = str(offer_id or "").strip()
        if not offer:
            raise RuntimeError("OFFER_ID_REQUIRED")

        if normalized_mode == "rollback":
            if not backup_path.exists():
                return {
                    "ok": False,
                    "status": "failed",
                    "reason": "offer_patch_backup_missing",
                    "mode": "rollback",
                    "scope": scope,
                    "offer_id": offer,
                }
            current_catalog = _read_bytes(catalog_path)
            backup_raw = backup_path.read_bytes()
            # Validate the backup before replacing the live catalog.
            parsed = yaml.safe_load(backup_raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise RuntimeError("OFFER_PATCH_BACKUP_INVALID")
            try:
                _atomic_write_text(catalog_path, backup_raw.decode("utf-8"))
                event_payload = {
                    "tenant_id": tenant,
                    "product_id": str(product),
                    "environment": str(env),
                    "scope": scope,
                    "offer_id": offer,
                    "mode": "rollback",
                }
                event = self.event_log.emit(
                    event_type="offer_patch_rolled_back@v1",
                    source="offer_catalog",
                    user_id=str(notify_user_id or "system"),
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    payload=event_payload,
                )
            except Exception:
                _restore_bytes(catalog_path, current_catalog)
                raise
            evidence = _ledger_evidence(
                code="offer_patch_rollback_recorded",
                event=event,
                fallback_ref=f"offer-patch-rollback:{scope}:{offer}:{decision_id}",
                payload=event_payload,
            )
            notification = _notify(
                self,
                decision_id=decision_id,
                correlation_id=correlation_id,
                tenant_id=tenant,
                user_id=notify_user_id,
                text=f"✅ Rollback выполнен: {offer}",
                callback_query_id=callback_query_id,
            )
            return {
                "ok": True,
                "status": "verified",
                "mode": "rollback",
                "scope": scope,
                "offer_id": offer,
                "notification": notification,
                "router_evidence": evidence,
            }

        raw = load_offer_catalog(catalog_path)
        offers = raw.get("offers") if isinstance(raw.get("offers"), list) else []
        target = locate_offer(offers=offers, offer_id=offer)
        before, after, changed = summarize_patch_application(
            target=target,
            patch=patch if isinstance(patch, dict) else {},
        )
        summary: dict[str, Any] = {
            "ok": True,
            "status": "dry_run" if normalized_mode == "dry_run" else "pending",
            "mode": normalized_mode,
            "scope": scope,
            "offer_id": offer,
            "changed": bool(changed),
            "before": before,
            "after": after,
        }
        if normalized_mode == "dry_run":
            summary["notification"] = _notify(
                self,
                decision_id=decision_id,
                correlation_id=correlation_id,
                tenant_id=tenant,
                user_id=notify_user_id,
                text=f"🧩 Patch preview\nОффер: {offer}\nChanged: {changed}",
                callback_query_id=callback_query_id,
            )
            return summary

        original_catalog = _read_bytes(catalog_path)
        original_backup = _read_bytes(backup_path)
        raw["offers"] = offers
        serialized = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)
        # Parse the serialized form before touching the live path.
        if not isinstance(yaml.safe_load(serialized), dict):
            raise RuntimeError("OFFER_PATCH_RESULT_INVALID")
        try:
            if original_catalog is not None:
                _atomic_write_text(
                    backup_path,
                    original_catalog.decode("utf-8"),
                )
            _atomic_write_text(catalog_path, serialized)
            event_payload = {
                "tenant_id": tenant,
                "product_id": str(product),
                "environment": str(env),
                "scope": scope,
                "offer_id": offer,
                "mode": "apply",
                "changed": bool(changed),
            }
            event = self.event_log.emit(
                event_type="offer_patch_applied@v1",
                source="offer_catalog",
                user_id=str(notify_user_id or "system"),
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload=event_payload,
            )
        except Exception:
            _restore_bytes(catalog_path, original_catalog)
            _restore_bytes(backup_path, original_backup)
            raise

        evidence = _ledger_evidence(
            code="offer_patch_apply_recorded",
            event=event,
            fallback_ref=f"offer-patch-apply:{scope}:{offer}:{decision_id}",
            payload=event_payload,
        )
        notification = _notify(
            self,
            decision_id=decision_id,
            correlation_id=correlation_id,
            tenant_id=tenant,
            user_id=notify_user_id,
            text=f"✅ Patch applied\nОффер: {offer}\nChanged: {changed}",
            callback_query_id=callback_query_id,
        )
        return {
            **summary,
            "status": "verified",
            "notification": notification,
            "router_evidence": evidence,
        }
