import pytest

from application.business_flows import bot_provisioning as bp
from application.business_flows import messenger_switching as ms

BOT = bp.Provisioning("r1", "studio_bot", bp.ProvisioningStatus.COMPLETED)
VK = {"platform": "vk", "status": "active", "connection_type": "vk_community", "external_account_id": "123"}


def test_destinations_only_from_unambiguous_active_targets():
    src = {"bots": [BOT, bp.Provisioning("r2", "x_bot", bp.ProvisioningStatus.FAILED)], "connections": [VK]}
    urls = [d.url for d in ms.public_destinations("lead_1", **src)]
    assert urls == ["https://t.me/studio_bot?start=lead_1", "https://vk.com/write-123?ref=lead_1"]
    two = {"bots": [BOT, bp.Provisioning("r3", "other_bot", bp.ProvisioningStatus.COMPLETED)], "connections": []}
    assert ms.public_target("telegram", **two) is None
    with pytest.raises(ValueError):
        ms.public_destination("telegram", "bad payload!", **src)


def test_staff_switch_roundtrip_and_rejection():
    cmd = ms.switch_command(42, "VK")
    assert cmd == "cpm:switch:vk:42" and ms.parse_switch_command(cmd) == ("vk", 42)
    assert ms.switch_destination(cmd, bots=[], connections=[VK]).public_target == "123"
    assert ms.switch_destination("nope", bots=[], connections=[]) is None
    with pytest.raises(ms.MessengerSwitchRejected):
        ms.switch_destination("cpm:switch:max:42", bots=[], connections=[VK])
    assert ms.available_switches(bots=[BOT], connections=[VK]) == ("telegram", "vk")
