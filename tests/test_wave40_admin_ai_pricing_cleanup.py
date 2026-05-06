from __future__ import annotations

from dataclasses import dataclass

from core.admin.ai_pricing import suggest_price_for_plan
from core.ai.world_state import WorldStateV1
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.handlers.admin.pricing import handle_pricing
from core.policies.telegram.handlers.admin.pricing_support import (
    pricing_approve_request_payload,
    pricing_edit_request_payload,
)


class _EventStore:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id, start_ms, end_ms, event_type):
        for ev in self._events:
            if ev.get("tenant_id") != tenant_id:
                continue
            if ev.get("event_type") != event_type:
                continue
            ts = int(ev.get("timestamp_ms") or 0)
            if ts < start_ms or ts > end_ms:
                continue
            yield ev


@dataclass
class _PM:
    last: dict | None = None

    def __call__(self, *, text, reply_markup):
        self.last = {"text": text, "reply_markup": reply_markup}
        return self.last


def _ctx(*, callback_data: str, tenant_id: str = "tenant-1", event_store=None):
    state = WorldStateV1(
        schema_version=1,
        user={},
        session={},
        product={},
        economy={},
        timestamp_ms=1,
        tenant_id=tenant_id,
        user_id="42",
    )
    ctx = TelegramCtx(
        state=state,
        text="",
        cmd=None,
        args="",
        callback_data=callback_data,
        callback_query_id="cq-1",
        settings={},
        city="",
        moods=[],
        admin_metrics={},
        is_admin=True,
        roles=[],
        perms=[],
        is_superadmin=False,
        realtime_state={},
        pricing_suggestions={},
        full_access=True,
        pay_status="ok",
        selected_tariff={},
        marketing_variants={},
        marketing_seed="",
        marketing_bandit={},
    )
    object.__setattr__(ctx, "event_store", event_store)
    return ctx


def test_ai_pricing_callback_uses_correct_prefix_and_returns_ai_reply():
    event_store = _EventStore([
        {
            "tenant_id": "tenant-1",
            "event_type": "tariff_selected",
            "user_id": "u1",
            "timestamp_ms": 1_000,
            "payload": {"plan_id": 1, "amount": 1000},
        },
        {
            "tenant_id": "tenant-1",
            "event_type": "payment_captured",
            "user_id": "u1",
            "timestamp_ms": 1_100,
            "payload": {},
        },
    ])
    ctx = _ctx(callback_data="admin:pricing:ai:1", event_store=event_store)
    pm = _PM()

    result = handle_pricing(ctx, pm=pm)

    assert result is not None
    assert "AI-подсказка цены" in result["text"]
    assert result["reply_markup"]["inline_keyboard"][0][0]["callback_data"].startswith("admin:pricing:ai_request:1:")


def test_suggest_price_for_plan_uses_explicit_now_ms_without_wall_clock_drift():
    event_store = _EventStore([
        {
            "tenant_id": "tenant-1",
            "event_type": "tariff_selected",
            "user_id": "u1",
            "timestamp_ms": 10_000,
            "payload": {"plan_id": 3, "amount": 1200},
        },
        {
            "tenant_id": "tenant-1",
            "event_type": "payment_captured",
            "user_id": "u1",
            "timestamp_ms": 10_100,
            "payload": {},
        },
    ])

    suggestion = suggest_price_for_plan(
        event_store,
        tenant_id="tenant-1",
        plan_id=3,
        base_price=1200,
        lookback_days=1,
        window_hours=1,
        now_ms=20_000,
    )

    assert suggestion.plan_id == 3
    assert suggestion.samples == 1
    assert suggestion.successes == 1


def test_pricing_session_payload_helpers_keep_single_session_contract():
    edit_payload = pricing_edit_request_payload(user_id="7", plan_id=12, callback_query_id="cq")
    approve_payload = pricing_approve_request_payload(user_id="7", request_id="req-1", callback_query_id="cq")

    assert edit_payload["key"] == "admin:pricing_session"
    assert approve_payload["key"] == "admin:pricing_session"
    assert edit_payload["value"]["stage"] == "await_price"
    assert approve_payload["value"]["stage"] == "await_approve_version"
