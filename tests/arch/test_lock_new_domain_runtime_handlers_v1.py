from __future__ import annotations
from pathlib import Path
from canon.domain_fs import scan_thin_runtime_handlers
ROOT = Path(__file__).resolve().parents[2]

def test_new_domain_runtime_handlers_are_thin() -> None:
    findings = scan_thin_runtime_handlers(ROOT)
    assert findings == [], [f"{item.kind}:{item.path}" for item in findings]
