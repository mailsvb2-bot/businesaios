from __future__ import annotations

from pathlib import Path

from scripts.apply_super_canon_v21 import _upsert_section


def test_upsert_section_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / 'doc.md'
    path.write_text('# Header\n', encoding='utf-8')

    block = (
        '<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:START -->\n'
        'HELLO\n'
        '<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:END -->'
    )

    _upsert_section(path, block)
    once = path.read_text(encoding='utf-8')

    _upsert_section(path, block)
    twice = path.read_text(encoding='utf-8')

    assert once == twice
    assert 'HELLO' in twice
