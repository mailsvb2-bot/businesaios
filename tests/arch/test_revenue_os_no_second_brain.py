from __future__ import annotations

from pathlib import Path

FORBIDDEN_TOKENS = (
    '.run(',
    '.execute(',
    'requests.',
    'httpx.',
    'aiohttp.',
    'DecisionCore(',
    'subprocess.',
    'socket.',
)


def test_revenue_os_is_advisory_only_and_has_no_hidden_execution() -> None:
    root = Path(__file__).resolve().parents[2]
    scanned = 0
    for path in root.joinpath('advisory', 'revenue_os').glob('*.py'):
        scanned += 1
        content = path.read_text(encoding='utf-8')
        for token in FORBIDDEN_TOKENS:
            assert token not in content, f'forbidden token {token!r} found in {path}'
    assert scanned >= 10


def test_adapter_docstring_declares_single_owner_boundary() -> None:
    root = Path(__file__).resolve().parents[2]
    adapter = root.joinpath('execution', 'revenue_os_adapter.py').read_text(encoding='utf-8')
    assert 'advisory_only' in adapter
    assert 'canonical DecisionCore path only' in adapter
