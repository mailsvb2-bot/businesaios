"""Paid ad media uses tenant-wide CAS budget and separate publication."""
from __future__ import annotations

import pytest

from application.business_flows import ad_media as media
from application.business_flows import visual_creatives as vc


class Store:
    def __init__(self):
        self.settings = {}
    def get_setting(self, *, tenant_id, key):
        return self.settings.get((tenant_id,key))
    def compare_and_set_setting(self, *, tenant_id, key, expected, value):
        k = (tenant_id,key)
        if self.settings.get(k) != expected:
            return False
        self.settings[k] = value
        return True

def config(limit="2", provider="yandexart"):
    return {"BAI_AD_MEDIA_GENERATION_ENABLED": "1",
            "BAI_AD_MEDIA_DAILY_LIMIT": limit,
            "BAI_AD_MEDIA_PROVIDER": provider}

def test_allowed_provider_only_and_disabled_without_budget():
    with pytest.raises(PermissionError):
        media.select_media_provider(config(provider="openai"))
    assert media.media_daily_limit(config(limit="0")) == 0
    assert not media.media_gen_enabled({})

def test_atomic_reservation_before_effect_and_idempotent_retry():
    store = Store()
    brief = vc.build_brief("Holiday campaign", context="", style="photo", fmt="post")
    calls = []
    def adapter(*args):
        return None
    media.register_media_provider("yandexart", adapter)

    def invoke(ad):
        calls.append(ad)
        assert len(store.settings) == 1
        return {"ok": True, "path": "provider://asset-1", "size": 1200}
    outcome, fact = media.generate_budgeted(facts=[], brief=brief, env=config(),
        event_store=store, tenant_id="tenant-a", now_ms=1800000000000, call=invoke)
    assert fact is not None and fact["published"] is False
    assert fact["path"] == "provider://asset-1"
    assert len(calls) == 1
    _, repeated = media.generate_budgeted(facts=[], brief=brief, env=config(),
        event_store=store, tenant_id="tenant-a", now_ms=1800000000000, call=invoke)
    assert repeated is None and len(calls) == 1

def test_exceptions_count_against_budget():
    store = Store()
    media.register_media_provider("yandexart", lambda *args: None)
    brief = vc.build_brief("Campaign B", context="", style="photo", fmt="post")
    _, fact = media.generate_budgeted(facts=[], brief=brief, env=config(limit="1"),
        event_store=store, tenant_id="t", now_ms=1800000000000,
        call=lambda adapter: (_ for _ in ()).throw(OSError("timeout")))
    assert fact["step"] == "media_charged" and fact["ok"] is False
    another = vc.build_brief("Campaign C", context="", style="photo", fmt="post")
    msg, fact = media.generate_budgeted(facts=[], brief=another, env=config(limit="1"),
        event_store=store, tenant_id="t", now_ms=1800000000000,
        call=lambda adapter: (_ for _ in ()).throw(AssertionError("must not call")))
    assert fact is None and "Лимит" in msg

def test_without_durable_store_no_provider_call():
    media.register_media_provider("yandexart", lambda *args: None)
    brief = vc.build_brief("Campaign D", context="", style="photo", fmt="post")
    message, fact = media.generate_budgeted(facts=[], brief=brief, env=config(),
        event_store=object(), tenant_id="t", now_ms=1800000000000,
        call=lambda adapter: (_ for _ in ()).throw(AssertionError()))
    assert fact is None and "атомарного" in message

def test_publication_requires_separate_yes():
    assert media.parse_media_publish("key | event | warmup | slot")[-1] is False
    assert media.parse_media_publish("key | event | warmup | slot | да")[-1] is True
    with pytest.raises(ValueError):
        media.parse_media_publish("key | event")
