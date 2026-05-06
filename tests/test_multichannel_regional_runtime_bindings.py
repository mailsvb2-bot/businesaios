from interfaces.messaging_runtime.channel_loader import load_bindings


def test_regional_runtime_bindings_are_available():
    bindings = load_bindings(enabled_channels=("line", "wechat", "kakaotalk"))
    channels = tuple(b.channel for b in bindings)
    assert channels == ("line", "wechat", "kakaotalk")
    assert bindings[0].render_capabilities["buttons"] is True
