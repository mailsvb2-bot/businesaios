from __future__ import annotations

import pathlib
import re


def test_policies_do_not_import_runtime_platform_directly():
    """Policies must not import adapters (prevents a second brain via side channels)."""
    base = pathlib.Path(__file__).resolve().parents[1]
    pol = base / 'core' / 'policies'
    assert pol.exists()

    bad = []
    for py in pol.rglob('*.py'):
        txt = py.read_text('utf-8', errors='ignore')
        if re.search(r'^\s*(from|import)\s+runtime\.platform', txt, flags=re.M):
            bad.append(str(py.relative_to(base)))
    assert not bad, 'Policies import runtime.platform directly: ' + ', '.join(bad)
