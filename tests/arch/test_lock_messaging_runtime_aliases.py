from pathlib import Path


def test_messaging_runtime_keeps_canonical_alias_map():
    text = Path('interfaces/messaging_runtime/channel_aliases.py').read_text(encoding='utf-8')
    assert "'web_chat': 'webchat'" in text
    assert "'api': 'api_gateway'" in text
