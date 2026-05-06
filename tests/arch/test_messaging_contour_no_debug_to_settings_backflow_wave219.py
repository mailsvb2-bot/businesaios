from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEBUG_ROOT = ROOT / 'interfaces/web/debug'

def test_debug_packages_do_not_start_importing_settings_ui_packages():
    offenders=[]
    for path in DEBUG_ROOT.rglob('*.py'):
        text=path.read_text(encoding='utf-8')
        if 'interfaces.web.settings.' in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, offenders
