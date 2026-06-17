from __future__ import annotations

"""
PRIVATE IMPLEMENTATION of EffectsPort.
SECURITY / ARCHITECTURE:
- System TZ: all real integrations must live in this module.
- Import this module only through runtime/effects.py or runtime/executor.py.
- It lives in runtime/_internal so that normal code paths cannot "accidentally" reach it.
- Real SDK clients (telegram/yookassa/http) must be imported ONLY here.
PAYMENTS NOTE:
- Provider create calls must use a stable *idempotence* key derived from a
  business order id (see core.payments.provider.idempotence_key_for_order).
"""
from dataclasses import dataclass
from typing import Any
from runtime.observability.telemetry import CANON_RUNTIME_TELEMETRY_OWNER as _CANON_RUNTIME_TELEMETRY_OWNER
CANON_RUNTIME_OBSERVABILITY_OWNER = _CANON_RUNTIME_TELEMETRY_OWNER

from runtime.platform.delivery_state import DeliveryState
from runtime.ports.effects import EffectsPort

from .effect_router import EffectRouter
from .effects_actions.llm_actions import LLMEffectsMixin
from .effects_actions.offer_patch_actions import OfferPatchEffectsMixin
from .effects_actions.payments_actions import PaymentsEffectsMixin
from .effects_actions.policy_actions import PolicyEffectsMixin
from .effects_actions.telegram_actions import TelegramEffectsMixin
from .effects_actions.weather_actions import WeatherEffectsMixin
from .effects_core import initialize_effects_runtime_state, throttled_emit_error
from .effects_domains.admin_state import AdminStateEffectsMixin
from .effects_domains.evolution import EvolutionEffectsMixin
from .effects_domains.marketing import MarketingEffectsMixin
from .effects_domains.tracking import TrackingEffectsMixin
from .effects_domains.user_state import UserStateEffectsMixin
from .http_transport import HttpTransport, build_http_transport, form_urlencode, url_with_params as _url_with_params


def _telegram_api_base() -> str:
    from runtime.platform.config.env_flags import env_str
    return env_str("TELEGRAM_API_BASE", "https://api.telegram.org").strip().rstrip("/")


def encode_form_body(data: dict[str, Any]) -> bytes:
    return form_urlencode(dict(data or {}))


def url_with_params(*, url: str, params: dict[str, Any] | None = None) -> str:
    return _url_with_params(url=url, params=params)


def start_yookassa_webhook_server_in_thread(*, host: str, port: int, path: str, event_store: Any, payment_outbox: Any) -> Any:
    import json
    import os
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    normalized_path = str(path or "/").strip() or "/"
    auth_mode = str(os.environ.get("YOOKASSA_WEBHOOK_AUTH_MODE", "")).strip().casefold()
    expected_token = str(os.environ.get("YOOKASSA_WEBHOOK_TOKEN", "")).strip()

    def _emit_event(payload: dict[str, Any]) -> None:
        if event_store is None:
            return
        append = getattr(event_store, "append", None) or getattr(event_store, "record", None)
        if callable(append):
            append(payload)

    def _enqueue(raw: dict[str, Any]) -> None:
        obj = raw.get("object") if isinstance(raw.get("object"), dict) else {}
        event_name = str(raw.get("event") or "yookassa.webhook")
        object_id = str(obj.get("id") or raw.get("id") or "unknown")
        payload = {"type": "yookassa_webhook", "payload": raw}
        enqueue_once = getattr(payment_outbox, "enqueue_once", None)
        if callable(enqueue_once):
            enqueue_once(dedupe_key=f"{event_name}:{object_id}", payload=payload)
            return
        enqueue = getattr(payment_outbox, "enqueue", None)
        if callable(enqueue):
            enqueue(payload)
            return
        items = getattr(payment_outbox, "items", None)
        if isinstance(items, list):
            items.append({"dedupe_key": f"{event_name}:{object_id}", "payload": payload})

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: Any) -> None:  # pragma: no cover - quiet smoke server
            return

        def _send_json(self, status_code: int, body: dict[str, Any]) -> None:
            raw = json.dumps(body).encode("utf-8")
            self.send_response(status_code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path != normalized_path:
                self._send_json(404, {"ok": False, "code": "not_found"})
                return
            if auth_mode == "token" and expected_token:
                observed_token = str(self.headers.get("X-Webhook-Token", "")).strip()
                if observed_token != expected_token:
                    self._send_json(401, {"ok": False, "code": "unauthorized"})
                    return
            size = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(size) if size > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._send_json(400, {"ok": False, "code": "invalid_json"})
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"ok": False, "code": "invalid_payload"})
                return
            _enqueue(payload)
            _emit_event({"type": "yookassa_webhook_received", "payload": payload})
            self._send_json(200, {"ok": True})

    server = ThreadingHTTPServer((str(host), int(port)), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@dataclass
class Effects(UserStateEffectsMixin, TrackingEffectsMixin, AdminStateEffectsMixin, MarketingEffectsMixin, EvolutionEffectsMixin, TelegramEffectsMixin, WeatherEffectsMixin, PaymentsEffectsMixin, LLMEffectsMixin, OfferPatchEffectsMixin, PolicyEffectsMixin, EffectsPort):
    event_log: Any
    policy_registry: Any
    delivery_state: DeliveryState | None = None
    payment_outbox: Any | None = None
    ledger: Any | None = None
    telegram_outbound_queue: Any | None = None
    settings_gateway: Any | None = None
    messaging_policy_event_store: Any | None = None
    messaging_policy_read_service: Any | None = None
    http_transport: HttpTransport | None = None
    effect_router: EffectRouter | None = None
    _last_sent: dict[str, float] = None  # type: ignore[assignment]
    _fail_count: int = 0
    _telegram_me: dict[str, Any] | None = None
    _telegram_webhook_cleared: bool = False
    _telegram_startup_checked: bool = False
    _last_err_ms: dict[str, int] | None = None
    _audio_delivery_keys: dict[str, float] | None = None
    _last_audio_sent_at: dict[str, float] | None = None
    _audio_lock: Any | None = None
    _min_audio_interval_s: float = 0.7
    def __post_init__(self):
        if self.http_transport is None:
            self.http_transport = build_http_transport()
        if self.effect_router is None:
            self.effect_router = EffectRouter(transport=self.http_transport, outbound_queue=self.telegram_outbound_queue)
        else:
            if getattr(self.effect_router, "transport", None) is None:
                self.effect_router.transport = self.http_transport
            if getattr(self.effect_router, "outbound_queue", None) is None:
                self.effect_router.outbound_queue = self.telegram_outbound_queue
        initialize_effects_runtime_state(self)
    def _throttled_emit_err(self, key: str, *, event_type: str, payload: dict[str, Any]) -> None:
        throttled_emit_error(
            event_log=self.event_log,
            cache=self._last_err_ms,
            key=str(key),
            event_type=str(event_type),
            payload=dict(payload),
        )
