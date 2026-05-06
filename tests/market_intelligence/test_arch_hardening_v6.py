from __future__ import annotations

from pathlib import Path


def test_market_intelligence_patch_has_no_raw_network_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    package_root = root / 'interfaces' / 'market_intelligence'
    forbidden = ('import requests', 'import httpx', 'import aiohttp', 'from requests', 'from httpx', 'import socket')
    scanned = 0
    for path in package_root.glob('*.py'):
        scanned += 1
        text = path.read_text(encoding='utf-8')
        for marker in forbidden:
            assert marker not in text, f'forbidden raw network import in {path.name}: {marker}'
    assert scanned >= 40


def test_market_intelligence_execution_has_no_decide_or_decisioncore() -> None:
    root = Path(__file__).resolve().parents[2]
    package_root = root / 'execution'
    target_files = sorted(package_root.glob('market_intelligence*.py')) + sorted((package_root / 'evidence').glob('market_intelligence.py'))
    scanned = 0
    for path in target_files:
        scanned += 1
        text = path.read_text(encoding='utf-8')
        assert 'DecisionCore' not in text
        assert '.decide(' not in text
        assert ' second brain ' not in f' {text.lower()} '
    assert scanned >= 10
