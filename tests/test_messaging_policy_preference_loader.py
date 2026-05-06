from runtime.messaging_policy.preference_loader import load_channel_preference


class _GW:
    def get_value(self, *, tenant_id: str, key: str):
        assert tenant_id == "tenant-x"
        assert key == "messaging:channel_preference"
        return {
            "primary": "email",
            "enabled": ["telegram", "email"],
            "verified": ["email"],
        }


def test_preference_loader_reads_saved_value():
    pref = load_channel_preference(
        settings_gateway=_GW(),
        tenant_id="tenant-x",
    )
    assert pref.primary == "email"
    assert pref.enabled == ("email", "telegram")
    assert pref.verified == ("email",)
