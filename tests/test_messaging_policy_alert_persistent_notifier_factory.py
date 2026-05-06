from runtime.messaging_policy_alert_dedup_persistent.boot import build_persistent_deduping_alert_notifier


class _GW:
    def __init__(self):
        self.items = {}

    def get_value(self, *, tenant_id: str, key: str):
        return self.items.get((tenant_id, key))

    def set_value(self, *, tenant_id: str, key: str, value: dict):
        self.items[(tenant_id, key)] = dict(value)


def test_build_persistent_deduping_alert_notifier():
    gw = _GW()
    out = build_persistent_deduping_alert_notifier(
        settings_gateway=gw,
        tenant_id="t1",
        cooldown_s=3600,
    )

    assert "store" in out
    assert "suppression_service" in out
    assert "mark_sent_service" in out
    assert "notifier" in out
