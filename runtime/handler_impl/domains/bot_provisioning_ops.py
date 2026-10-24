"""Tenant Telegram bot lifecycle (BotFather + Managed Bots): provisioning, finalize, owner controls.

Split out of business_flow_ops. Tokens exist only as env:/vault: references; every Telegram call goes
through the executor's ``telegram_self_check`` effect.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.business_flows import bot_provisioning as botprov
from application.business_flows.projection import flow_payloads
from runtime.handler_impl.core.payloads import require_mapping, required_str
from runtime.handler_impl.domains.business_flow_ops import send_tracked


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


_BOT_STATUS_RU = {
    "awaiting_secret": "ожидает токен (передайте его через защищённую форму владельца)",
    "ready": "токен получен, ожидает проверки",
    "verifying": "идёт проверка бота",
    "completed": "подключён",
    "failed": "ошибка проверки — можно повторить",
    "cancelled": "отменён",
    "awaiting_bot": "ожидает создания бота в Telegram",
    "disabled": "приостановлен (включить: /bot_activate)",
    "revoked": "отозван",
}


def handle_bot_provisioning(payload, effects, env, *, event_store, vault=None, token_source=None):
    """Tenant bot lifecycle. Tokens exist only as env:/vault: refs; effects go through the executor.

    ``token_source(external_bot_id) -> str`` is the Managed Bots token fetch (injected; absent -> refused).
    """
    body = require_mapping(payload or {})
    tenant_id, user_id = required_str(body, "tenant_id"), required_str(body, "user_id")
    op, arg = str(body.get("op") or "status"), str(body.get("arg") or "")
    state = botprov.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="bot_provisioning@v1"))
    current, owned = botprov.active(state), botprov.owned(state)
    try:
        if op == "request":
            change = botprov.request(state, tenant_id=tenant_id, user_id=user_id, username=arg)
            text = (
                f"🤖 Заявка на подключение @{change['username']} создана.\nСтатус: {_BOT_STATUS_RU['awaiting_secret']}"
            )
        elif op in _MANAGED_OPS:
            change, text = _MANAGED_OPS[op](body, state, effects, tenant_id, user_id, vault, token_source)
        elif op == "cancel":
            if current is None:
                raise ValueError("bot_provisioning_not_found")
            change = botprov.transition(current, "cancel")
            text = f"🤖 Подключение @{current.username or 'бота'} отменено."
        elif op in {"disable", "activate", "revoke"}:
            if owned is None:
                raise ValueError("bot_provisioning_not_found")
            change, text = _owner_op(op, owned, effects, tenant_id, vault)
        elif op in {"attach", "verify"}:
            if current is None:
                raise ValueError("bot_provisioning_not_found")
            if op == "attach":
                change = botprov.transition(current, "secret_attached", credential_ref=arg.strip())
                text = f"🤖 Ссылка на токен для @{current.username} сохранена. Проверить: /verify_bot"
            else:
                change = _verify_bot(current, effects, tenant_id=tenant_id, vault=vault)
                text = _verify_text(current, change)
        else:
            change = None
            shown = current or owned
            text = (
                "🤖 Активных подключений нет.\nСоздать: /connect_bot имя_бота"
                if shown is None
                else f"🤖 @{shown.username or '—'}: {_BOT_STATUS_RU[shown.status.value]}"
            )
    except ValueError as exc:
        return send_tracked(
            body, effects, env, text=f"🤖 Не получилось: {exc}", event_type=None, event_payload=None, ok=True, reason=""
        )
    return send_tracked(
        body, effects, env, text=text, event_type="bot_provisioning@v1" if change else None, event_payload=change
    )


def managed_bot_token_source(effects):
    """Production token source: Bot API getManagedBotToken through the sealed Telegram effect."""

    def fetch(external_bot_id: str) -> str:
        res = effects.telegram_managed_bot_token(managed_bot_id=str(external_bot_id))
        if not isinstance(res, dict) or res.get("ok") is not True or not str(res.get("token") or "").strip():
            raise ValueError(str((res or {}).get("error") or "managed_bot_token_unavailable")[:60])
        return str(res["token"]).strip()

    return fetch


def _verify_text(item, change) -> str:
    if change["status"] == "completed":
        return f"🤖 @{item.username} подключён (getMe подтвердил бота, вебхук снят — работает через polling)."
    return f"🤖 Проверка @{item.username} не прошла: {change.get('error_code')}. Повтор: /connect_bot"


def _resolve_token(item, *, tenant_id: str, vault) -> str:
    from runtime.integration import managed_bot_credentials as mbc

    try:
        return str(mbc.resolve(item.credential_ref, tenant_id=tenant_id, vault=vault) or "").strip()
    except Exception:  # noqa: BLE001 - never surface secret-adjacent errors
        return ""


def _self_check(item, effects, *, tenant_id: str, vault) -> tuple[str, int]:
    """('', bot_id) on success, else (error_code, 0). getMe + polling-only webhook removal via the effect."""
    token = _resolve_token(item, tenant_id=tenant_id, vault=vault)
    if not token:
        return f"credential_unresolved:{item.credential_ref.partition(':')[0] or 'none'}", 0
    try:
        report = effects.telegram_self_check(token=token, clear_webhook=True)
    except Exception as exc:
        return str(exc).split(":")[0][:60] or "getme_failed", 0
    error = botprov.identity_error(item, report)
    return error, 0 if error else int((report.get("bot") or {}).get("id") or 0)


def _verify_bot(current, effects, *, tenant_id: str = "", vault=None) -> dict[str, Any]:
    """Donor finalize: verify identity, drop webhook (polling-only); any failure -> ``failed`` with a code."""
    error, bot_id = _self_check(current, effects, tenant_id=tenant_id, vault=vault)
    if error:
        return botprov.transition(current, "failed", error_code=error)
    return {
        **botprov.transition(current, "verified"),
        "bot_id": bot_id,
        "external_bot_id": current.external_bot_id or str(bot_id),
    }


def _owner_op(op, owned, effects, tenant_id, vault):
    """Donor managed_bot_owner: disable/revoke are plain facts; activate is re-verified first and
    otherwise leaves the bot disabled (rollback = no state change)."""
    if op == "activate":
        if owned.status is not botprov.ProvisioningStatus.DISABLED:
            raise ValueError("managed_bot_not_disabled")
        error, _ = _self_check(owned, effects, tenant_id=tenant_id, vault=vault)
        if error:
            return None, f"🤖 @{owned.username} не включён: {error}. Бот остаётся приостановленным."
        return botprov.transition(owned, "activated"), f"🤖 @{owned.username} снова работает."
    if op == "disable":
        return botprov.transition(owned, "disable"), f"🤖 @{owned.username} приостановлен. Включить: /bot_activate"
    from runtime.integration import managed_bot_credentials as mbc

    change = botprov.transition(owned, "revoke")
    if owned.credential_ref.startswith(f"vault:{mbc.NAMESPACE}."):
        # Donor _revoke_managed_bot_and_credential: a managed-bot token becomes unrecoverable.
        change["credential_retired"] = mbc.discard(vault, owned.credential_ref, tenant_id=tenant_id)
    return change, f"🤖 @{owned.username} отозван; токен выведен из хранилища."


def _managed_begin(body, state, effects, tenant_id, user_id, vault, token_source):
    change = botprov.begin_managed(state, tenant_id=tenant_id, user_id=user_id, now_ms=_now_ms())
    if change is None:
        return None, "🤖 Заявка уже создана — завершите создание бота в Telegram."
    return change, "🤖 Создайте бота в Telegram по кнопке менеджера ботов; подключение продолжится автоматически."


def _managed_pending(user_id, state):
    item = botprov.pending_for_user(state, user_id)
    if item is None:
        raise ValueError("managed_bot_request_not_found")
    return item


def _managed_created(body, state, effects, tenant_id, user_id, vault, token_source):
    item = _managed_pending(user_id, state)
    change = botprov.record_created(
        item,
        external_bot_id=str(body.get("external_bot_id") or ""),
        username=str(body.get("username") or ""),
        event_ms=int(body["event_ms"]) if body.get("event_ms") is not None else None,
    )
    return change, f"🤖 Бот @{botprov.normalize_username(str(body.get('username') or ''))} создан, получаю токен."


def _managed_complete(body, state, effects, tenant_id, user_id, vault, token_source):
    """Donor complete_telegram_managed_bot_onboarding: fetch token -> seal in vault -> attach ref -> verify.
    On verification failure the sealed token is deactivated (rollback) and the request is ``failed``."""
    from runtime.integration import managed_bot_credentials as mbc

    item = _managed_pending(user_id, state)
    if item.status is not botprov.ProvisioningStatus.AWAITING_SECRET or not item.external_bot_id:
        raise ValueError("managed_bot_identity_not_recorded")
    if token_source is None:
        raise ValueError("managed_bot_token_source_unavailable")
    try:
        token = token_source(item.external_bot_id)
    except Exception:  # noqa: BLE001 - token fetch errors may echo secrets
        raise ValueError("managed_bot_token_fetch_failed") from None
    ref = mbc.seal(vault, tenant_id=tenant_id, external_bot_id=item.external_bot_id, token=token)
    botprov.transition(item, "secret_attached", credential_ref=ref)  # validates the reference shape
    ready = replace(item, status=botprov.ProvisioningStatus.READY, credential_ref=ref)
    final = _verify_bot(ready, effects, tenant_id=tenant_id, vault=vault)
    if final["status"] != "completed":
        mbc.discard(vault, ref, tenant_id=tenant_id)
        final = {**final, "credential_ref": "", "rolled_back": True}
    return {**final, "credential_ref": final.get("credential_ref", ref)}, _verify_text(ready, final)


def _managed_event(body, state, effects, tenant_id, user_id, vault, token_source):
    """Telegram ``managed_bot`` update (arg ``"<bot_id> <username>"``): record the identity, then complete.

    One fact is stored: the completion carries the identity, so a failed verification still keeps it."""
    bot_id, _, username = str(body.get("arg") or "").strip().partition(" ")
    created = _managed_created({"external_bot_id": bot_id, "username": username.strip()}, state, effects,
                               tenant_id, user_id, vault, token_source)[0]  # fmt: skip
    if created is None:  # duplicate update for an already recorded identity
        return _managed_complete(body, state, effects, tenant_id, user_id, vault, token_source)
    item = state[created["request_id"]]
    state = {**state, item.request_id: replace(item, status=botprov.ProvisioningStatus.AWAITING_SECRET,
                                               username=created["username"], external_bot_id=created["external_bot_id"])}  # fmt: skip
    change, text = _managed_complete(body, state, effects, tenant_id, user_id, vault, token_source)
    return {**change, "username": created["username"], "external_bot_id": created["external_bot_id"]}, text


_MANAGED_OPS = {
    "managed_event": _managed_event,
    "managed_begin": _managed_begin,
    "managed_created": _managed_created,
    "managed_complete": _managed_complete,
}
