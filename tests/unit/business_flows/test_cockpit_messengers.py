from __future__ import annotations

from application.business_flows import bot_provisioning as bp
from application.business_flows import cockpit as cp
from runtime.handler_impl.domains.business_flow_ops import _messenger_connections

BOT = bp.Provisioning("r1", "lotos_bot", bp.ProvisioningStatus.COMPLETED)
VK = {"platform": "vk", "status": "active", "connection_type": "vk_community", "external_account_id": "123"}


def _r(data: str, **kw):
    return cp.render(cp.parse(data), cp.Snapshot(bots=[BOT], **kw), is_owner=True)


def _cbs(rows):
    return [cb for row in rows for _, cb in row]


def test_messengers_screen_offers_unambiguous_switches_for_viewer() -> None:
    text, rows = _r("cpm:messengers", viewer_id=42, connections=[VK])
    assert "@lotos_bot" in text and "VK — active" in text
    assert {"cpm:switch:telegram:42", "cpm:switch:vk:42"} <= set(_cbs(rows))
    assert not any(c.startswith("cpm:switch") for c in _cbs(_r("cpm:messengers")[1]))  # unknown viewer


def test_switch_screen_links_target_and_rejects_foreign_or_missing() -> None:
    assert "https://t.me/lotos_bot?start=staff42" in _r("cpm:switch:telegram:42", viewer_id=42)[0]
    assert "https://vk.com/write-123?ref=staff42" in _r("cpm:switch:vk:42", viewer_id=42, connections=[VK])[0]
    assert "неактуальна" in _r("cpm:switch:telegram:7", viewer_id=42)[0]
    assert "недоступен" in _r("cpm:switch:max:42", viewer_id=42)[0]


def test_native_routes_become_connection_rows_without_token_refs() -> None:
    facts = [
        {"step": "nm_lease", "route_id": "nm_1", "platform": "vk", "external_id": "123", "owner": "o", "until_ms": 9},
        {"step": "nm_active", "route_id": "nm_1", "token_ref": "vault:vk/1"},
    ]
    assert _messenger_connections(facts) == [VK]
