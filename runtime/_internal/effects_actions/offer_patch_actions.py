"""Governed offer-catalog preview, apply, and rollback effects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from runtime._internal.effects_actions.offer_patch_apply_support import (
    load_offer_catalog,
    locate_offer,
    resolve_offer_catalog,
    suggest_patch_for_action,
    summarize_patch_application,
)
from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime._internal.offer_catalog_mutation import (
    acquire_catalog_lock,
    atomic_replace_bytes,
    build_locked_transaction,
    restore_optional_bytes,
)
from runtime.security.runtime_asserts import assert_called_from_executor


def _event_id(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("event_id") or "").strip()
    return str(getattr(event, "event_id", "") or "").strip()


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
    channel: str,
    channel_policy: dict[str, Any] | None,
) -> Any:
    if not user_id:
        return None
    try:
        return owner.send_message(
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            text=str(text)[:3500],
            reply_markup=None,
            callback_query_id=callback_query_id,
            channel=str(channel),
            channel_policy=(
                dict(channel_policy)
                if isinstance(channel_policy, dict)
                else None
            ),
            priority="normal",
            critical=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "notification_failed",
            "error": exc.__class__.__name__,
        }


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
        channel: str = "telegram",
        channel_policy: dict[str, Any] | None = None,
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
            channel=channel,
            channel_policy=channel_policy,
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
        channel: str = "telegram",
        channel_policy: dict[str, Any] | None = None,
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
            backup_raw = backup_path.read_bytes()
            parsed = yaml.safe_load(backup_raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise RuntimeError("OFFER_PATCH_BACKUP_INVALID")
            mutation_lock = acquire_catalog_lock(catalog_path)
            transaction = None
            try:
                if not catalog_path.exists():
                    raise RuntimeError(f"OFFER_CATALOG_NOT_FOUND:{catalog_path}")
                transaction = build_locked_transaction(
                    catalog_path=catalog_path,
                    prepared_bytes=backup_raw,
                    original_catalog=catalog_path.read_bytes(),
                    mutation_lock=mutation_lock,
                    tmp_suffix=".offerpatch.rollback.tmp",
                    error_prefix="OFFER_PATCH",
                )
                transaction.apply()
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
                if transaction is not None and transaction.applied:
                    transaction.rollback()
                raise
            finally:
                if transaction is not None:
                    transaction.finalize()
                elif not mutation_lock.released:
                    mutation_lock.release()
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
                channel=channel,
                channel_policy=channel_policy,
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

        if normalized_mode == "dry_run":
            raw = load_offer_catalog(catalog_path)
            offers = raw.get("offers") if isinstance(raw.get("offers"), list) else []
            target = locate_offer(offers=offers, offer_id=offer)
            before, after, changed = summarize_patch_application(
                target=target,
                patch=patch if isinstance(patch, dict) else {},
            )
            summary: dict[str, Any] = {
                "ok": True,
                "status": "dry_run",
                "mode": "dry_run",
                "scope": scope,
                "offer_id": offer,
                "changed": bool(changed),
                "before": before,
                "after": after,
            }
            summary["notification"] = _notify(
                self,
                decision_id=decision_id,
                correlation_id=correlation_id,
                tenant_id=tenant,
                user_id=notify_user_id,
                text=f"🧩 Patch preview\nОффер: {offer}\nChanged: {changed}",
                callback_query_id=callback_query_id,
                channel=channel,
                channel_policy=channel_policy,
            )
            return summary

        mutation_lock = acquire_catalog_lock(catalog_path)
        transaction = None
        original_backup = backup_path.read_bytes() if backup_path.exists() else None
        try:
            if not catalog_path.exists():
                raise RuntimeError(f"OFFER_CATALOG_NOT_FOUND:{catalog_path}")
            original_catalog = catalog_path.read_bytes()
            raw = load_offer_catalog(catalog_path)
            offers = raw.get("offers") if isinstance(raw.get("offers"), list) else []
            target = locate_offer(offers=offers, offer_id=offer)
            before, after, changed = summarize_patch_application(
                target=target,
                patch=patch if isinstance(patch, dict) else {},
            )
            raw["offers"] = offers
            serialized = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)
            if not isinstance(yaml.safe_load(serialized), dict):
                raise RuntimeError("OFFER_PATCH_RESULT_INVALID")
            transaction = build_locked_transaction(
                catalog_path=catalog_path,
                prepared_bytes=serialized.encode("utf-8"),
                original_catalog=original_catalog,
                mutation_lock=mutation_lock,
                tmp_suffix=".offerpatch.apply.tmp",
                error_prefix="OFFER_PATCH",
            )
            atomic_replace_bytes(
                backup_path,
                original_catalog,
                suffix=".backup.tmp",
                invalidate=False,
            )
            transaction.apply()
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
            if transaction is not None and transaction.applied:
                transaction.rollback()
            restore_optional_bytes(
                backup_path,
                original_backup,
                suffix=".backup.restore.tmp",
            )
            raise
        finally:
            if transaction is not None:
                transaction.finalize()
            elif not mutation_lock.released:
                mutation_lock.release()

        summary = {
            "ok": True,
            "status": "verified",
            "mode": "apply",
            "scope": scope,
            "offer_id": offer,
            "changed": bool(changed),
            "before": before,
            "after": after,
        }
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
            channel=channel,
            channel_policy=channel_policy,
        )
        return {
            **summary,
            "notification": notification,
            "router_evidence": evidence,
        }

