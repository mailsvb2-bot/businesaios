from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from runtime._internal.effects_actions.telegram.messaging_parts.tracking import emit_warning
from runtime.messaging.bridge import get_multichannel_effects_bridge
from runtime.messaging.delivery_result import DeliveryResult
from runtime.observability.telemetry import telegram_api_span
from runtime.platform.config.env_flags import env_float


def _stable_metadata(msg) -> dict[str, Any]:
    return {
        "channel": str(msg.channel),
        "tenant_id": str(msg.tenant_id),
        "user_id": str(msg.user_id),
        "decision_id": str(msg.decision_id),
        "correlation_id": str(msg.correlation_id),
        "payload_digest": getattr(msg, "payload_digest", None),
    }


def _receipt(state: Any, *, delivery_key: str) -> dict[str, Any] | None:
    if state is None or not hasattr(state, "get_receipt"):
        return None
    try:
        value = state.get_receipt(str(delivery_key))
    except Exception:
        return None
    return dict(value or {}) if isinstance(value, Mapping) else None


def _mark_accepted(state: Any, *, delivery_key: str, msg, meta: Mapping[str, Any]) -> None:
    if state is None or not hasattr(state, "mark_accepted"):
        return
    payload_digest = meta.get("payload_digest") or getattr(msg, "payload_digest", None)
    receipt_meta = {**_stable_metadata(msg), **dict(meta or {}), "delivery_phase": "accepted_for_delivery"}
    try:
        state.mark_accepted(
            str(delivery_key),
            payload_digest=None if payload_digest is None else str(payload_digest),
            metadata=receipt_meta,
        )
    except Exception:
        return


def _mark_delivered(state: Any, *, delivery_key: str, msg, meta: Mapping[str, Any]) -> None:
    if state is None or not hasattr(state, "mark_delivered"):
        return
    external_id = meta.get("external_id")
    payload_digest = meta.get("payload_digest") or getattr(msg, "payload_digest", None)
    receipt_meta = {**_stable_metadata(msg), **dict(meta or {}), "delivery_phase": "finalized"}
    try:
        state.mark_delivered(
            str(delivery_key),
            external_id=None if external_id is None else str(external_id),
            payload_digest=None if payload_digest is None else str(payload_digest),
            metadata=receipt_meta,
        )
    except Exception:
        return


def telegram_pre_send(self, *, msg) -> None:
    if isinstance(msg.callback_query_id, str) and msg.callback_query_id.strip():
        try:
            self._telegram_answer_callback(
                msg.callback_query_id.strip(),
                user_id=msg.user_id,
                decision_id=msg.decision_id,
                correlation_id=msg.correlation_id,
            )
        except Exception as exc:
            emit_warning(self.event_log, user_id=msg.user_id, decision_id=msg.decision_id, correlation_id=msg.correlation_id, reason="answer_callback_failed", error=exc)
    if isinstance(msg.callback_query_id, str) and msg.callback_query_id.strip():
        try:
            self._telegram_send_chat_action(chat_id=str(msg.user_id), action="typing")
        except Exception as exc:
            emit_warning(self.event_log, user_id=msg.user_id, decision_id=msg.decision_id, correlation_id=msg.correlation_id, reason="chat_action_failed", error=exc)


def telegram_throttle(self, *, user_id: str, decision_id: str, correlation_id: str) -> None:
    if self.telegram_outbound_queue is not None:
        return
    min_interval = float(env_float("TELEGRAM_MIN_MSG_INTERVAL_S", 0.25, lo=0.0, hi=30.0))
    now = time.time()
    last = float(self._last_sent.get(str(user_id), 0.0))
    dt = now - last
    if dt < float(min_interval):
        try:
            time.sleep(float(min_interval) - dt)
        except Exception as exc:
            emit_warning(self.event_log, user_id=user_id, decision_id=decision_id, correlation_id=correlation_id, reason="sleep_throttle_failed", error=exc)
    self._last_sent[str(user_id)] = time.time()


def telegram_delivery(self, *, msg) -> tuple[bool, dict]:
    delivery_key = msg.delivery_key
    existing = _receipt(getattr(self, "delivery_state", None), delivery_key=delivery_key)
    if existing is not None:
        phase = str(existing.get("delivery_phase") or existing.get("metadata", {}).get("delivery_phase") or "finalized")
        return True, {"channel": msg.channel, "dedup": True, "delivery_key": delivery_key, "receipt": existing, "payload_digest": getattr(msg, "payload_digest", None), "delivery_phase": phase, "delivery_finalized": phase == "finalized"}
    with telegram_api_span(event_log=self.event_log, user_id=str(msg.user_id), decision_id=str(msg.decision_id), correlation_id=str(msg.correlation_id)):
        ok, meta = self._telegram_send_message(
            chat_id=msg.user_id,
            text=msg.text,
            reply_markup=msg.reply_markup,
            priority=msg.priority,
            critical=msg.critical,
        )
    out = dict(meta or {})
    out["delivery_key"] = delivery_key
    out.setdefault("payload_digest", getattr(msg, "payload_digest", None))
    mode = str(out.get("mode") or "")
    finalized = bool(ok) and mode not in {"queued", "noop"}
    out["delivery_finalized"] = finalized
    if finalized:
        _mark_delivered(getattr(self, "delivery_state", None), delivery_key=delivery_key, msg=msg, meta=out)
    elif bool(ok) and mode == "queued":
        out["delivery_phase"] = "accepted_for_delivery"
        _mark_accepted(getattr(self, "delivery_state", None), delivery_key=delivery_key, msg=msg, meta=out)
    return bool(ok), out


def multichannel_delivery(*, msg) -> tuple[bool, dict]:
    result = get_multichannel_effects_bridge().send(msg)
    if not isinstance(result, DeliveryResult):
        raise RuntimeError("INVALID_DELIVERY_RESULT")
    meta = dict(result.detail or {})
    meta["external_id"] = result.external_id
    meta["mode"] = result.mode
    meta["payload_digest"] = getattr(msg, "payload_digest", None)
    meta["delivery_key"] = msg.delivery_key
    meta["delivery_finalized"] = bool(result.ok) and str(result.mode or "") not in {"queued", "accepted"}
    return bool(result.ok), meta


def build_single_sender(self):
    def _send_one(selected_msg):
        if selected_msg.channel == "telegram":
            telegram_pre_send(self, msg=selected_msg)
            telegram_throttle(
                self,
                user_id=selected_msg.user_id,
                decision_id=selected_msg.decision_id,
                correlation_id=selected_msg.correlation_id,
            )
            return telegram_delivery(self, msg=selected_msg)
        return multichannel_delivery(msg=selected_msg)
    return _send_one
