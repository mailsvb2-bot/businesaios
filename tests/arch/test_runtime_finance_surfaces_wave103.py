from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGETS = [
    ROOT / "runtime" / "handlers" / "finance_build.py",
    ROOT / "runtime" / "handlers" / "finance_explain.py",
    ROOT / "runtime" / "boot" / "finance_boot_registry.py",
    ROOT / "runtime" / "boot" / "finance_boot_runtime.py",
]


def test_runtime_finance_surfaces_use_public_api_wave103() -> None:
    for path in TARGETS:
        text = path.read_text(encoding="utf-8")
        assert "from runtime.finance import" in text, path.name
        assert "from core.finance" not in text, path.name
