from runtime.messaging.channel_preference import ChannelPreference


def test_verified_channels_are_subset_of_enabled():
    pref = ChannelPreference(primary="telegram", enabled=("telegram",), verified=("whatsapp", "telegram"))
    assert pref.verified == ("telegram",)
