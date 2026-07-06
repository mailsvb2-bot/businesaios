from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from runtime._internal.effect_evidence_contract import effect_result_to_evidence, evidence_contract_fields
from runtime._internal.effect_payloads import normalize_effect_payload, payload_contract_fields
from runtime._internal.effect_results import canonical_effect_result, result_contract_fields
from runtime._internal.effect_types import EffectActionType, require_effect_action_type
from runtime._internal.effects_actions.llm_completion_support import call_marketing_llm
from runtime._internal.effects_actions.telegram.startup import telegram_self_check_effect
from runtime._internal.effects_actions.telegram_actions_polling import poll_telegram_updates_effect
from runtime._internal.effects_clients.weather_client import open_meteo_weather
from runtime._internal.effects_clients.yookassa_client import create_payment, get_payment_status
from runtime._internal.http_transport import HttpTransport, build_http_transport

EffectHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
@dataclass(slots=True)
class EffectRouter:
    transport: HttpTransport | None = None
    outbound_queue: Any | None = None
    delivery_state: Any | None = None
    _handlers: dict[EffectActionType, EffectHandler] = field(init=False, repr=False, default_factory=dict)
    def __post_init__(self) -> None:
        if self.transport is None:
            self.transport = build_http_transport()
        self._register_default_handlers()
    def register(self, action_type: str | EffectActionType, handler: EffectHandler) -> None:
        key = require_effect_action_type(action_type)
        self._handlers[key] = handler
    def supported_action_types(self) -> tuple[str, ...]:
        return tuple(sorted(str(item) for item in self._handlers))
    def supported_action_enums(self) -> tuple[EffectActionType, ...]:
        return tuple(sorted(self._handlers.keys(), key=str))
    def payload_contracts(self) -> dict[str, tuple[str, ...]]:
        contracts = payload_contract_fields()
        return {str(key): tuple(contracts.get(key, ())) for key in sorted(self._handlers.keys(), key=str)}
    def result_contract_fields(self) -> tuple[str, ...]:
        return result_contract_fields()
    def evidence_contract_fields(self) -> tuple[str, ...]:
        return evidence_contract_fields()
    def has_handler(self, action_type: str | EffectActionType) -> bool:
        try:
            key = require_effect_action_type(action_type)
        except RuntimeError:
            return False
        return key in self._handlers
    async def execute(self, action_type: str | EffectActionType, payload: dict[str, Any]) -> dict[str, Any]:
        key = require_effect_action_type(action_type)
        data = normalize_effect_payload(key, payload)
        handler = self._handlers.get(key)
        if handler is None:
            raise RuntimeError(f"unsupported_effect_action:{str(key)}")
        try:
            raw_result = await handler(data)
        except RuntimeError:
            raise
        except Exception as exc:
            raw_result = {"ok": False, "error": f"{exc.__class__.__name__}:{exc}", "status": "failure"}
        result = canonical_effect_result(key, raw_result)
        result["evidence"] = effect_result_to_evidence(key, result)
        return result
    def _register_default_handlers(self) -> None:
        self.register(EffectActionType.TELEGRAM_SEND_MESSAGE, self._handle_telegram_send_message)
        self.register(EffectActionType.TELEGRAM_SEND_AUDIO, self._handle_telegram_send_audio)
        self.register(EffectActionType.TELEGRAM_ANSWER_CALLBACK, self._handle_telegram_answer_callback)
        self.register(EffectActionType.TELEGRAM_SEND_CHAT_ACTION, self._handle_telegram_send_chat_action)
        self.register(EffectActionType.PAYMENTS_YOOKASSA_CREATE, self._handle_yookassa_create_payment)
        self.register(EffectActionType.PAYMENTS_YOOKASSA_GET_STATUS, self._handle_yookassa_get_payment_status)
        self.register(EffectActionType.CRM_WRITE_RECORD, self._handle_generic_post_json)
        self.register(EffectActionType.ADS_UPDATE_BUDGET, self._handle_generic_post_json)
        self.register(EffectActionType.WEBSITE_PUBLISH_PAGE, self._handle_generic_post_json)
        self.register(EffectActionType.WEATHER_OPEN_METEO_CURRENT, self._handle_weather_current)
        self.register(EffectActionType.LLM_MARKETING_COMPLETE, self._handle_marketing_llm_complete)
        self.register(EffectActionType.TELEGRAM_SELF_CHECK, self._handle_telegram_self_check)
        self.register(EffectActionType.TELEGRAM_POLL_UPDATES, self._handle_telegram_poll_updates)
    def _telegram_client(self):
        from runtime._internal.effects_clients.telegram_client import TelegramClient
        attempts = (
            {"outbound_queue": self.outbound_queue, "transport": self.transport, "delivery_state": self.delivery_state},
            {"outbound_queue": self.outbound_queue, "delivery_state": self.delivery_state},
            {"outbound_queue": self.outbound_queue},
        )
        last_error: TypeError | None = None
        for kwargs in attempts:
            try:
                return TelegramClient(**kwargs)
            except TypeError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        return TelegramClient(outbound_queue=self.outbound_queue)
    async def _handle_telegram_send_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._telegram_client()
        ok, meta = client.send_message(
            chat_id=str(payload.get("chat_id") or ""),
            text=str(payload.get("text") or ""),
            reply_markup=payload.get("reply_markup") if isinstance(payload.get("reply_markup"), dict) else None,
            priority=payload.get("priority", "normal"),
            critical=bool(payload.get("critical", True)),
            timeout_s=int(payload.get("timeout_s") or 30),
        )
        return {"ok": bool(ok), **dict(meta or {})}
    async def _handle_telegram_send_audio(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._telegram_client()
        ok, meta = client.send_audio(
            chat_id=str(payload.get("chat_id") or ""),
            audio_url=str(payload.get("audio_url") or ""),
            caption=_optional_text(payload.get("caption")),
            priority=payload.get("priority", "normal"),
            critical=bool(payload.get("critical", True)),
            timeout_s=int(payload.get("timeout_s") or 60),
        )
        return {"ok": bool(ok), **dict(meta or {})}
    async def _handle_telegram_answer_callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._telegram_client().answer_callback_query(
            str(payload.get("callback_query_id") or ""),
            text=_optional_text(payload.get("text")),
            show_alert=bool(payload.get("show_alert", False)),
        )
        return {"ok": True, "mode": "best_effort"}
    async def _handle_telegram_send_chat_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._telegram_client().send_chat_action(
            chat_id=str(payload.get("chat_id") or ""),
            action=str(payload.get("action") or "typing"),
        )
        return {"ok": True, "mode": "best_effort"}
    async def _handle_yookassa_create_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        ok, meta = await asyncio.to_thread(
            create_payment,
            amount_rub=payload["amount_rub"],
            description=str(payload.get("description") or "Payment"),
            customer_id=str(payload.get("customer_id") or ""),
            idempotence_key=(_optional_text(payload.get("idempotence_key"))),
            metadata=dict(payload.get("metadata") or {}),
            timeout_s=int(payload.get("timeout_s") or 30),
            transport=self.transport,
        )
        return {"ok": bool(ok), **dict(meta or {})}
    async def _handle_yookassa_get_payment_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = await asyncio.to_thread(
            get_payment_status,
            external_payment_id=str(payload.get("external_payment_id") or ""),
            timeout_s=int(payload.get("timeout_s") or 20),
            transport=self.transport,
        )
        return {"ok": True, "status": str(status)}
    async def _handle_weather_current(self, payload: dict[str, Any]) -> dict[str, Any]:
        ok, text, meta = await asyncio.to_thread(
            open_meteo_weather,
            str(payload.get("city") or "").strip() or "Amsterdam",
            transport=self.transport,
        )
        return {"ok": bool(ok), "text": str(text or ""), "meta": dict(meta or {})}
    async def _handle_marketing_llm_complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await asyncio.to_thread(
            call_marketing_llm,
            provider=str(payload.get("provider") or ""),
            system=str(payload.get("system") or "You write concise marketing copy."),
            user=str(payload.get("user") or ""),
            model=(_optional_text(payload.get("model"))),
        )
        return dict(result or {})
    async def _handle_telegram_self_check(self, payload: dict[str, Any]) -> dict[str, Any]:
        class _RuntimeView:
            def __init__(self, router: EffectRouter) -> None:
                self.http_transport = router.transport
                self._telegram_startup_checked = False
                self._telegram_me = None
        runtime_view = _RuntimeView(self)
        return await asyncio.to_thread(
            telegram_self_check_effect,
            runtime_view,
            token=_optional_text(payload.get("token")),
        )
    async def _handle_telegram_poll_updates(self, payload: dict[str, Any]) -> dict[str, Any]:
        class _RuntimeView:
            def __init__(self, router: EffectRouter) -> None:
                self.http_transport = router.transport
                self._telegram_startup_checked = bool(payload.get("startup_checked", False))
                self._telegram_webhook_cleared = bool(payload.get("webhook_cleared", False))
        runtime_view = _RuntimeView(self)
        return await asyncio.to_thread(
            poll_telegram_updates_effect,
            runtime_view,
            offset=payload.get("offset"),
            timeout_s=int(payload.get("timeout_s") or 30),
            limit=int(payload.get("limit") or 50),
        )
    async def _handle_generic_post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = _optional_text(payload.get("url")) or _optional_text(payload.get("endpoint"))
        if url is None:
            raise RuntimeError("effect_router_missing_endpoint")
        headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else dict(payload.get("payload") or payload)
        response = await self.transport.post_json(
            url=str(url),
            headers={str(k): str(v) for k, v in dict(headers).items()},
            data=dict(data or {}),
            timeout_s=int(payload.get("timeout_s") or 30),
        )
        return {
            "ok": 200 <= int(response.status) < 300,
            "status_code": int(response.status),
            "json": response.json,
            "text": response.text,
        }
