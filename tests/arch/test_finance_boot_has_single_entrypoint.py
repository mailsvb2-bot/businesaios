from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_legacy_register_strategic_finance_file_exists() -> None:
    assert not (ROOT / "runtime" / "boot" / "register_strategic_finance.py").exists()


def test_finance_boot_exports_attachment_helpers() -> None:
    text = (ROOT / "runtime" / "boot" / "finance_boot.py").read_text(encoding="utf-8")
    assert "def attach_finance_runtime(" in text
    assert "def build_finance_job_registry(" in text
    assert "def build_finance_event_registry(" in text
