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
from .http_transport import HttpTransport, build_http_transport


def _telegram_api_base() -> str:
    from runtime.platform.config.env_flags import env_str
    return env_str("TELEGRAM_API_BASE", "https://api.telegram.org").strip().rstrip("/")
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
