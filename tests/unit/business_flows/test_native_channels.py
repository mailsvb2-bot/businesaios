from __future__ import annotations

import json

import pytest

from application.business_flows import native_channels as nc
from application.business_flows import promotions as pm
from runtime.integration.native_messenger_inbound import handle_inbound, promotion_touch

KEY = "k" * 40
BASE = "https://bai.example.ru"


class Fake:
    def __init__(self, fail: bool = False) -> None:
        self.fail, self.calls = fail, []

    def verify_community(self, gid):
        return {"name": "Студия"}

    def get_callback_confirmation_code(self, gid):
        return "abc123"

    def ensure_callback_server(self, *, group_id, url, secret):
        self.calls.append((url, secret))
        if self.fail:
            raise OSError("down")

    def get_me(self):
        return {"user_id": 77, "first_name": "Бот", "username": "studio_bot"}

    def ensure_webhook_subscription(self, *, url, secret):
        self.calls.append((url, secret))


def test_base_url_and_refs() -> None:
    for bad in ["http://x.ru", "https://x.ru:8443", "https://x.ru/p", "https://u:p@x.ru", "https://x.ru?q=1"]:
        with pytest.raises(ValueError):
            nc.public_base_url(bad)
    with pytest.raises(ValueError, match="ссылкой"):
        nc.provision_vk(
            group_id=1,
            token_ref="raw-token",
            provider=Fake(),
            base_url=BASE,
            server_key=KEY,
            routes={},
            owner="o",
            now_ms=0,
        )
    with pytest.raises(ValueError, match="positive"):
        nc.provision_vk(
            group_id="-1",
            token_ref="env:VK",
            provider=Fake(),
            base_url=BASE,
            server_key=KEY,
            routes={},
            owner="o",
            now_ms=0,
        )


def test_vk_lifecycle_lease_failure_and_inbound() -> None:
    p = Fake()
    facts, url = nc.provision_vk(
        group_id="42", token_ref="env:VK", provider=p, base_url=BASE, server_key=KEY, routes={}, owner="o", now_ms=0
    )
    routes = nc.replay(facts)
    ((rid, r),) = routes.items()
    assert r.status == "active" and url.endswith(f"/vk/{rid}") and p.calls[0][1] == nc.webhook_secret(KEY, rid)
    assert KEY not in json.dumps(facts) and p.calls[0][1] not in json.dumps(facts)
    held = nc.replay([nc.acquire_lease({}, platform="vk", external_id="9", owner="a", now_ms=0)])
    with pytest.raises(ValueError, match="уже"):
        nc.acquire_lease(held, platform="vk", external_id="9", owner="b", now_ms=1000)
    nc.acquire_lease(held, platform="vk", external_id="9", owner="b", now_ms=nc.LEASE_MS + 1)
    bad, url2 = nc.provision_vk(
        group_id="9",
        token_ref="env:VK",
        provider=Fake(fail=True),
        base_url=BASE,
        server_key=KEY,
        routes={},
        owner="o",
        now_ms=0,
    )
    assert url2 is None and nc.replay(bad)[bad[0]["route_id"]].status == "disabled"
    kw = {"routes": routes, "platform": "vk", "rid": rid, "server_key": KEY, "tenant_id": "t"}
    assert handle_inbound(payload={"type": "confirmation", "group_id": 42}, **kw) == ("confirm", "abc123")
    assert handle_inbound(payload={"type": "message_new", "group_id": 42, "secret": "x"}, **kw) == (
        "rejected",
        "secret_invalid",
    )
    assert handle_inbound(payload={"type": "message_new", "group_id": 1}, **kw)[1] == "group_mismatch"
    secret = nc.webhook_secret(KEY, rid)
    ok = {"type": "message_new", "group_id": 42, "secret": secret, "object": {"message": {"from_id": 5, "text": "hi"}}}
    kind, ev = handle_inbound(payload=ok, **kw)
    assert kind == "event" and ev.channel == "vk"
    routes2 = nc.replay([*facts, nc.disable(routes, rid)])
    assert handle_inbound(payload=ok, **{**kw, "routes": routes2})[1] == "route_inactive"


def test_max_provision_and_secret_header() -> None:
    facts, _ = nc.provision_max(
        token_ref="vault:MAX", provider=Fake(), base_url=BASE, server_key=KEY, routes={}, owner="o", now_ms=0
    )
    routes = nc.replay(facts)
    ((rid, r),) = routes.items()
    assert r.username == "studio_bot" and r.external_id == "77"
    kw = {
        "routes": routes,
        "platform": "max",
        "rid": rid,
        "server_key": KEY,
        "tenant_id": "t",
        "payload": {"message": {"text": "x"}},
    }
    assert handle_inbound(secret_header="no", **kw)[0] == "rejected"
    assert handle_inbound(secret_header=nc.webhook_secret(KEY, rid), **kw)[0] == "event"


def test_open_channel_promotion() -> None:
    camps = pm.replay([{"step": "promotion_saved", "promotion_id": "pr1", "slot_id": "s1", "channel": "vk", "source_token": "tok12345abcd",
                        "creative": {"creative_id": "c", "headline": "h", "primary_text": "p", "description": "d"}}])  # fmt: skip
    ids = {("vk", "5"): "cust-5"}
    fact = promotion_touch(
        camps=camps, text=f"/start {pm.PREFIX}tok12345abcd", platform="vk", subject="5", identities=ids
    )
    assert fact and fact["customer_id"] == "cust-5" and fact["step"] == "promotion_opened"
    with pytest.raises(ValueError, match="идентичности"):
        promotion_touch(camps=camps, text=f"{pm.PREFIX}tok12345abcd", platform="max", subject="5", identities=ids)
    with pytest.raises(ValueError, match="активного"):
        pm.open_channel(camps, "tok12345abcd", customer_id="x", active_customers=set())
    assert promotion_touch(camps=camps, text="hello", platform="vk", subject="5", identities=ids) is None
