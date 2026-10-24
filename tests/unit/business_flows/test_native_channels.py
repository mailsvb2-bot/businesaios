from __future__ import annotations

import json

import pytest

from application.business_autonomy.provider_catalog import provider_map
from application.business_flows import native_channels as nc
from application.business_flows import promotions as pm
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from runtime.integration.native_messenger_inbound import persist_route_secrets, promotion_touch
from security.secret_vault import InMemorySecretVault

SC = {"tenant_id": "t", "business_id": "b"}

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
            **SC,
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
            **SC,
        )


def test_vk_lifecycle_lease_failure_and_inbound() -> None:
    p = Fake()
    facts, url = nc.provision_vk(
        group_id="42", token_ref="env:VK", provider=p, base_url=BASE, server_key=KEY, routes={}, owner="o", now_ms=0, **SC
    )
    routes = nc.replay(facts)
    ((rid, r),) = routes.items()
    assert r.status == "active" and url.endswith("/vk_messaging") and p.calls[0][1] == nc.webhook_secret(KEY, rid)
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
        **SC,
    )
    assert url2 is None and nc.replay(bad)[bad[0]["route_id"]].status == "disabled"
    assert url == f"{BASE}/providers/webhook/t/b/vk_messaging"
    vault, rt, vk = InMemorySecretVault(), None, provider_map()["vk_messaging"]
    secret = nc.webhook_secret(KEY, rid)
    names = persist_route_secrets(vault, platform="vk", **SC, webhook_secret=secret, confirmation_code=r.confirmation_code, group_id="42")
    assert secret not in json.dumps(names)
    rt = ProviderWebhookRuntime(secret_vault=vault)
    conf = json.dumps({"type": "confirmation", "group_id": 42}).encode()
    assert rt.response_body(provider=vk, **SC, body=conf) == "abc123"
    bad = json.dumps({"type": "message_new", "secret": "x"}).encode()
    good = json.dumps({"type": "message_new", "secret": secret}).encode()
    assert not rt.verify(provider=vk, **SC, headers={}, body=bad)
    assert rt.verify(provider=vk, **SC, headers={}, body=good)


def test_max_provision_and_secret_header() -> None:
    facts, _ = nc.provision_max(
        token_ref="vault:MAX", provider=Fake(), base_url=BASE, server_key=KEY, routes={}, owner="o", now_ms=0, **SC
    )
    routes = nc.replay(facts)
    ((rid, r),) = routes.items()
    assert r.username == "studio_bot" and r.external_id == "77"
    vault, mx = InMemorySecretVault(), provider_map()["max_messaging"]
    persist_route_secrets(vault, platform="max", **SC, webhook_secret=nc.webhook_secret(KEY, rid))
    rt = ProviderWebhookRuntime(secret_vault=vault)
    assert not rt.verify(provider=mx, **SC, headers={"X-Max-Bot-Api-Secret": "no"}, body=b"{}")
    assert rt.verify(provider=mx, **SC, headers={"X-Max-Bot-Api-Secret": nc.webhook_secret(KEY, rid)}, body=b"{}")


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


def test_promotion_touch_hook_vk_max_only() -> None:
    from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
    from runtime.integration.native_messenger_inbound import promotion_touch_hook

    camps = pm.replay([{"step": "promotion_saved", "promotion_id": "pr1", "slot_id": "s1", "channel": "vk", "source_token": "tok12345abcd",
                        "creative": {"creative_id": "c", "headline": "h", "primary_text": "p", "description": "d"}}])  # fmt: skip
    hook = promotion_touch_hook(lambda t, b: (camps, {("vk", "5"): "cust-5"}))
    assert hook("t", "b", "vk_messaging", "5", f"/start {pm.PREFIX}tok12345abcd")["customer_id"] == "cust-5"
    assert hook("t", "b", "telegram", "5", f"/start {pm.PREFIX}tok12345abcd") is None
    assert "promotion_touch_hook" in ProviderInboundWebhookService.__dataclass_fields__


# ---- e-mail SMTP connections (event-sourced port of email_connections) ----
def test_email_provision_stores_refs_only_and_is_idempotent() -> None:
    conn, facts = nc.provision_email_smtp(sender_email=" Owner@Example.RU ", smtp_host="smtp.example.ru", smtp_port=465,
                                          username_ref="env:SMTP_USER", password_ref="vault:SMTP_PASS", security="ssl",
                                          sender_name="Студия")
    assert conn.status == "pending" and conn.sender_email == "owner@example.ru" and conn.id.startswith("ec_")
    assert "hunter2" not in json.dumps(facts)
    conns = nc.email_replay(facts)
    assert nc.provision_email_smtp(sender_email="owner@example.ru", smtp_host="smtp.example.ru", smtp_port=465,
                                   username_ref="env:SMTP_USER", password_ref="vault:SMTP_PASS")[0].id == conn.id
    assert nc.email_replay(facts + facts).keys() == conns.keys()


@pytest.mark.parametrize("bad", [
    dict(username_ref="plain-user"), dict(password_ref="hunter2"), dict(smtp_port=0), dict(smtp_port=70000),
    dict(sender_email="not-an-email"), dict(security="none"), dict(smtp_host=""),
])
def test_email_provision_rejects_raw_secrets_and_bad_input(bad) -> None:
    args = dict(sender_email="o@example.ru", smtp_host="smtp.example.ru", smtp_port=465, username_ref="env:U",
                password_ref="env:P", security="ssl")
    with pytest.raises(ValueError):
        nc.provision_email_smtp(**{**args, **bad})


def test_email_activation_needs_a_passing_probe() -> None:
    conn, facts = nc.provision_email_smtp(sender_email="o@example.ru", smtp_host="smtp.example.ru", smtp_port=587,
                                          username_ref="env:U", password_ref="env:P", security="starttls")
    conns = nc.email_replay(facts)

    def refuse(c):
        raise RuntimeError("535 auth failed")

    with pytest.raises(RuntimeError):
        nc.verify_and_activate_email_smtp(conns, conn.id, refuse)
    assert nc.email_replay(facts)[conn.id].status == "pending"
    seen = []
    active, fs = nc.verify_and_activate_email_smtp(conns, conn.id, seen.append)
    assert active.status == "active" and seen[0].id == conn.id
    assert nc.email_replay(facts + fs)[conn.id].status == "active"
    again, fs2 = nc.verify_and_activate_email_smtp(nc.email_replay(facts + fs), conn.id, seen.append)
    assert again.status == "active" and len(seen) == 2  # re-verification probes again (credentials may have rotated)
    with pytest.raises((LookupError, ValueError)):
        nc.verify_and_activate_email_smtp(conns, "ec_missing", seen.append)
