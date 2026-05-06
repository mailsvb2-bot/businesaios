from __future__ import annotations

from pathlib import Path

def test_no_connector_direct_delivery():
    for path in Path('demand_capture/sources').glob('*.py'):
        src = path.read_text(encoding='utf-8')
        assert '.deliver(' not in src
