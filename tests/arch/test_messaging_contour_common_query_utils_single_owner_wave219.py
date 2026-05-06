from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / 'interfaces/web/debug/common/query_utils.py'

def test_common_query_utils_is_single_owner_for_clean_text_and_clamp_int():
    if not COMMON.exists():
        raise AssertionError('interfaces/web/debug/common/query_utils.py missing')
    text = COMMON.read_text(encoding='utf-8')
    assert 'def clean_text(' in text
    assert 'def clamp_int(' in text
    offenders=[]
    for path in (ROOT / 'interfaces/web/debug').rglob('*.py'):
        rel=path.relative_to(ROOT).as_posix()
        if rel == 'interfaces/web/debug/common/query_utils.py':
            continue
        src=path.read_text(encoding='utf-8')
        if 'def clean_text(' in src or 'def clamp_int(' in src:
            offenders.append(rel)
    assert not offenders, offenders
