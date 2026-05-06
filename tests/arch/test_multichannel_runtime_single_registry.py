from pathlib import Path


def test_no_parallel_registry_implementations_diverge() -> None:
    root = Path(__file__).resolve().parents[2]
    channel_registry = root / "interfaces" / "messaging_runtime" / "channel_registry.py"
    text = channel_registry.read_text(encoding="utf-8")
    assert "from .registry import ChannelRegistry" in text
