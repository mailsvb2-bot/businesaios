from __future__ import annotations
from pathlib import Path
from canon.domain_fs import scan_boot_wiring_only
ROOT = Path(__file__).resolve().parents[2]

def test_new_domain_boot_modules_are_wiring_only() -> None:
    findings = scan_boot_wiring_only(ROOT)
    assert findings == [], [f"{item.kind}:{item.path}" for item in findings]
