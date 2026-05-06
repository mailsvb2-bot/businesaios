from __future__ import annotations

from pathlib import Path

from canon.domain_fs import scan_boot_wiring_only, scan_thin_runtime_handlers


ROOT = Path(__file__).resolve().parents[2]


def test_marked_thin_runtime_handlers_remain_small() -> None:
    findings = scan_thin_runtime_handlers(ROOT)
    assert findings == [], [f"{i.kind}:{i.path}" for i in findings]


def test_marked_boot_modules_are_wiring_only() -> None:
    findings = scan_boot_wiring_only(ROOT)
    assert findings == [], [f"{i.kind}:{i.path}" for i in findings]
