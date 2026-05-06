from __future__ import annotations

from pathlib import Path


def test_runtime_boot_phases_use_observability_not_print() -> None:
    path = Path('runtime/boot/boot_phases.py')
    text = path.read_text(encoding='utf-8')
    assert 'emit_boot_diagnostic_lines' in text
    assert 'print(' not in text
