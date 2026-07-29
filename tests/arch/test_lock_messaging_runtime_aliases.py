from pathlib import Path


def test_messaging_runtime_delegates_channel_normalization_to_runtime_owner():
    text = Path("interfaces/messaging_runtime/channel_aliases.py").read_text(
        encoding="utf-8"
    )
    assert (
        "from runtime.messaging.channel_normalizer import normalize_channel"
        in text
    )
    assert "CANONICAL_CHANNEL_ALIASES" not in text
    assert "return normalize_channel(channel)" in text
