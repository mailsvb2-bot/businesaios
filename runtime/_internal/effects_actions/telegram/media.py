from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_actions.telegram.delivery_evidence import build_delivery_evidence
from runtime._internal.effects_actions.telegram.transport import telegram_send_audio_transport
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def _mark_accepted(state: Any, *, audio_id: str, meta: Mapping[str, Any], user_id: str) -> None:
    if state is None or not hasattr(state, "mark_accepted"):
        return
    try:
        state.mark_accepted(
            str(audio_id),
            payload_digest=None if meta.get("payload_digest") is None else str(meta.get("payload_digest")),
            metadata={"method": "sendAudio", "chat_id": str(user_id), **dict(meta or {}), "delivery_phase": "accepted_for_delivery"},
        )
    except Exception:
        return


def _mark_delivered(state: Any, *, audio_id: str, meta: Mapping[str, Any], user_id: str) -> None:
    if state is None or not hasattr(state, "mark_delivered"):
        return
    try:
        state.mark_delivered(
            str(audio_id),
            external_id=None if meta.get("external_id") is None else str(meta.get("external_id")),
            payload_digest=None if meta.get("payload_digest") is None else str(meta.get("payload_digest")),
            metadata={"method": "sendAudio", "chat_id": str(user_id), **dict(meta or {}), "delivery_phase": "finalized"},
        )
    except Exception:
        return


def _existing_receipt(state: Any, *, audio_id: str) -> dict[str, Any] | None:
    if state is None or not hasattr(state, "get_receipt"):
        return None
    try:
        receipt = state.get_receipt(str(audio_id))
    except Exception:
        return None
    return dict(receipt or {}) if isinstance(receipt, Mapping) else None


def send_audio_effect(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    user_id: str,
    path: str,
    kind: str = "voice",
    caption: str | None = None,
    channel: str = "telegram",
) -> dict:
    assert_called_from_executor()
    if channel != "telegram":
        meta = {"channel": channel, "mode": "noop", "delivery_finalized": False}
        return {
            "ok": True,
            "meta": meta,
            "evidence": build_delivery_evidence(
                ok=True,
                meta=meta,
                action_type=str(EffectActionType.TELEGRAM_SEND_AUDIO),
            ),
        }

    try:
        if effects._audio_lock is not None and effects._last_audio_sent_at is not None:
            with effects._audio_lock:
                last = float(effects._last_audio_sent_at.get(str(user_id), 0.0))
                now = time.monotonic()
                delta = now - last
            if delta < float(effects._min_audio_interval_s or 0.0):
                time.sleep(max(0.0, float(effects._min_audio_interval_s) - delta))
            with effects._audio_lock:
                effects._last_audio_sent_at[str(user_id)] = time.monotonic()
    except Exception:
        swallow(__name__, "runtime/_internal/_effects_impl.py")

    audio_id = f"telegram_audio:{user_id}:{decision_id}:{str(kind or 'voice')}:{str(path)}"

    def _deliver() -> tuple[bool, dict]:
        return telegram_send_audio_transport(
            effects,
            chat_id=str(user_id),
            audio_url=str(path),
            caption=caption,
            priority="normal",
        )

    if effects.delivery_state is None and effects._audio_lock is not None and effects._audio_delivery_keys is not None:
        try:
            with effects._audio_lock:
                if audio_id in effects._audio_delivery_keys:
                    ok, meta = True, {"channel": channel, "dedup": True, "mode": "memory", "delivery_finalized": True}
                else:
                    now = time.monotonic()
                    for key, timestamp in list(effects._audio_delivery_keys.items()):
                        if (now - float(timestamp)) > 3600.0:
                            effects._audio_delivery_keys.pop(key, None)
                    effects._audio_delivery_keys[audio_id] = now
                    ok, meta = _deliver()
        except Exception:
            ok, meta = _deliver()
    elif effects.delivery_state is not None:
        existing = _existing_receipt(effects.delivery_state, audio_id=audio_id)
        if existing is not None:
            phase = str(existing.get("delivery_phase") or existing.get("metadata", {}).get("delivery_phase") or "finalized")
            ok, meta = True, {
                "channel": channel,
                "dedup": True,
                "receipt": existing,
                "delivery_phase": phase,
                "delivery_finalized": phase == "finalized",
            }
        else:
            ok, meta = _deliver()
            mode = str((meta or {}).get("mode") or "")
            finalized = bool(ok) and mode not in {"queued", "noop"}
            meta = {**dict(meta or {}), "delivery_finalized": finalized}
            if finalized:
                _mark_delivered(effects.delivery_state, audio_id=audio_id, meta=meta, user_id=str(user_id))
            elif bool(ok) and mode == "queued":
                meta["delivery_phase"] = "accepted_for_delivery"
                _mark_accepted(effects.delivery_state, audio_id=audio_id, meta=meta, user_id=str(user_id))
    else:
        ok, meta = _deliver()

    meta = dict(meta or {})
    meta.setdefault("delivery_key", audio_id)
    if "delivery_finalized" not in meta:
        mode = str(meta.get("mode") or "")
        meta["delivery_finalized"] = bool(ok) and mode not in {"queued", "noop", "accepted"}
    if bool(ok) and str(meta.get("mode") or "") == "queued":
        meta.setdefault("delivery_phase", "accepted_for_delivery")

    effects.event_log.emit(
        event_type="audio_sent",
        source="runtime_effects",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={"ok": bool(ok), "path": str(path), "kind": str(kind or "voice"), "meta": meta},
    )
    return {
        "ok": bool(ok),
        "meta": meta,
        "evidence": build_delivery_evidence(
            ok=bool(ok),
            meta=meta,
            action_type=str(EffectActionType.TELEGRAM_SEND_AUDIO),
        ),
    }


__all__ = ["send_audio_effect"]
