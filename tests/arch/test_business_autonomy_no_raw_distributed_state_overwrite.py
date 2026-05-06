from __future__ import annotations

from pathlib import Path


def test_business_autonomy_no_raw_distributed_state_overwrite() -> None:
    target = Path(__file__).resolve().parents[2] / 'application' / 'business_autonomy' / 'guarded_service.py'
    text = target.read_text(encoding='utf-8')
    assert '_write_document_state(' in text
    assert 'business_autonomy_distributed_state_version_conflict' in text
