from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import core.admin.read_model as read_model
import core.policies.telegram.handlers.admin.analytics as sut


class BrokenRow:
    def get(self, key, default=None):
        raise RuntimeError("broken row")


def ctx(**overrides):
    values = {
        "callback_data": "",
        "is_admin": True,
        "admin_metrics": {},
        "event_store": object(),
        "moods": [],
        "cmd": None,
        "args": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def pm():
    return Mock(side_effect=lambda **kwargs: kwargs)


@pytest.mark.parametrize(
    "callback",
    [
        "admin:demo:brief",
        "admin:demo:full",
        "admin:users:today",
        "admin:segments",
        "admin:ab",
        "admin:giftshare",
        "admin:funnel2",
        "admin:funnel",
        "admin:latency",
        "admin:retention",
        "admin:user:card",
        "admin:state:last",
    ],
)
def test_every_admin_callback_denies_non_admin(callback):
    render = pm()
    result = sut.handle_analytics(
        ctx(callback_data=callback, is_admin=False), user_id="a", pm=render
    )
    assert result["text"] == "Доступ запрещён."


def test_demo_brief_and_full_cover_metric_sources():
    render = pm()
    brief = sut.handle_analytics(
        ctx(
            callback_data="admin:demo:brief",
            admin_metrics={
                "demo_summary": {"sent_work": 2, "sent_home": 3, "users": 4}
            },
        ),
        user_id="a",
        pm=render,
    )
    assert "Сводка (кратко)" in brief["text"]
    assert "Пользователей (30д): 4" in brief["text"]

    full = sut.handle_analytics(
        ctx(callback_data="admin:demo:full", admin_metrics=None),
        user_id="a",
        pm=render,
    )
    assert "Сводка (подробно)" in full["text"]
    assert "Всего отправок: 0" in full["text"]


def test_users_today_with_mapping_and_empty_metrics():
    render = pm()
    result = sut.handle_analytics(
        ctx(callback_data="admin:users:today", admin_metrics={"users_today": 9}),
        user_id="a",
        pm=render,
    )
    assert result["text"].endswith("9")

    empty = sut.handle_analytics(
        ctx(callback_data="admin:users:today", admin_metrics=None),
        user_id="a",
        pm=render,
    )
    assert empty["text"].endswith("0")


def test_segments_ab_giftshare_and_funnel2(monkeypatch):
    monkeypatch.setattr(
        read_model,
        "segments_summary",
        lambda store, days: {
            "new_users": 1,
            "active_users_7d": 2,
            "payers_30d": 3,
            "granted_30d": 4,
        },
    )
    monkeypatch.setattr(
        read_model,
        "ab_offers_summary",
        lambda store, days: {"variants_set": 5, "variants_chosen": 2},
    )
    monkeypatch.setattr(
        read_model,
        "giftshare_summary",
        lambda store, days: {"share_clicked": 6, "gift_sent": 7},
    )
    monkeypatch.setattr(
        read_model,
        "funnel2_report",
        lambda store, days: {
            "counts": {
                "tariffs_viewed": 10,
                "tariff_selected": 8,
                "payment_created": 6,
                "payment_captured": 4,
                "access_granted": 3,
                "audio_sent": 2,
            },
            "rates_pct_from_view": {
                "tariff_selected": 80,
                "payment_created": 60,
                "payment_captured": 40,
                "access_granted": 30,
                "audio_sent": 20,
            },
        },
    )
    render = pm()

    segments = sut.handle_analytics(
        ctx(callback_data="admin:segments"), user_id="a", pm=render
    )
    assert "Новые сегодня: 1" in segments["text"]
    ab = sut.handle_analytics(ctx(callback_data="admin:ab"), user_id="a", pm=render)
    assert "Сгенерировано вариантов: 5" in ab["text"]
    gift = sut.handle_analytics(
        ctx(callback_data="admin:giftshare"), user_id="a", pm=render
    )
    assert "Отправлено подарков: 7" in gift["text"]
    funnel = sut.handle_analytics(
        ctx(callback_data="admin:funnel2"), user_id="a", pm=render
    )
    assert "Оплата успешна: 4 (40%)" in funnel["text"]


def test_funnel_mapping_and_non_mapping_sources():
    render = pm()
    populated = sut.handle_analytics(
        ctx(
            callback_data="admin:funnel",
            admin_metrics={
                "funnel": {
                    "tariffs_viewed": 1,
                    "tariff_selected": 2,
                    "payment_created": 3,
                    "payment_succeeded": 4,
                    "access_granted": 5,
                    "audio_sent": 6,
                }
            },
        ),
        user_id="a",
        pm=render,
    )
    assert "Отправок контента: 6" in populated["text"]

    empty = sut.handle_analytics(
        ctx(callback_data="admin:funnel", admin_metrics="invalid"),
        user_id="a",
        pm=render,
    )
    assert "Тарифы: просмотрели — 0" in empty["text"]


def test_latency_empty_rows_valid_rows_and_broken_rows():
    render = pm()
    empty = sut.handle_analytics(
        ctx(callback_data="admin:latency", admin_metrics=None),
        user_id="a",
        pm=render,
    )
    assert "Данных пока нет" in empty["text"]

    result = sut.handle_analytics(
        ctx(
            callback_data="admin:latency",
            admin_metrics={
                "latency": {
                    "window_days": 14,
                    "samples": 3,
                    "top_slowest": [
                        {
                            "button": "buy",
                            "p50_ms": 10,
                            "p95_ms": 20,
                            "max_ms": 30,
                            "count": 3,
                        },
                        BrokenRow(),
                    ],
                }
            },
        ),
        user_id="a",
        pm=render,
    )
    assert "окно 14д" in result["text"]
    assert "buy — p50 10мс" in result["text"]
    assert "broken" not in result["text"]


def test_retention_mapping_and_non_mapping_sources():
    render = pm()
    result = sut.handle_analytics(
        ctx(
            callback_data="admin:retention",
            admin_metrics={"retention": {"users": 12, "active_2d": 8}},
        ),
        user_id="a",
        pm=render,
    )
    assert "Пользователей (30д): 12" in result["text"]

    empty = sut.handle_analytics(
        ctx(callback_data="admin:retention", admin_metrics=[]),
        user_id="a",
        pm=render,
    )
    assert "Активны ≥2 дней (30д): 0" in empty["text"]


def test_user_card_instruction():
    result = sut.handle_analytics(
        ctx(callback_data="admin:user:card"), user_id="a", pm=pm()
    )
    assert "/user <telegram_id>" in result["text"]


def test_last_state_empty_note_no_note_and_broken_item():
    render = pm()
    empty = sut.handle_analytics(
        ctx(callback_data="admin:state:last", moods=[]), user_id="a", pm=render
    )
    assert empty["text"] == "Пока нет отмеченных состояний."

    result = sut.handle_analytics(
        ctx(
            callback_data="admin:state:last",
            moods=[
                {"score": 4, "note": "line one\nline two"},
                {"score": 7, "note": ""},
                BrokenRow(),
            ],
        ),
        user_id="a",
        pm=render,
    )
    assert "4/10 — line one line two" in result["text"]
    assert "• 7/10" in result["text"]


def test_user_command_all_validation_paths():
    render = pm()
    denied = sut.handle_analytics(
        ctx(cmd="/user", is_admin=False), user_id="admin", pm=render
    )
    assert denied["text"] == "Доступ запрещён."

    missing = sut.handle_analytics(
        ctx(cmd="/user", args="  "), user_id="admin", pm=render
    )
    assert missing["text"] == "Используй: /user <telegram_id>"

    invalid = sut.handle_analytics(
        ctx(cmd="/user", args="abc rest"), user_id="admin", pm=render
    )
    assert invalid["text"].startswith("ID должен быть числом")

    action = sut.handle_analytics(
        ctx(cmd="/user", args="123 extra"), user_id="admin", pm=render
    )
    assert action.action == "admin_user_card@v1"
    assert action.payload == {"admin_id": "admin", "target_user_id": "123"}


def test_unmatched_input_returns_none():
    assert (
        sut.handle_analytics(
            ctx(callback_data="other", cmd="/other"), user_id="a", pm=pm()
        )
        is None
    )
