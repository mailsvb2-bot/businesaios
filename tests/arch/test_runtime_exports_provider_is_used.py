from pathlib import Path


def test_runtime_integration_keeps_inline_runtime_exports_provider_marker() -> None:
    path = Path("boot/runtime_integration.py")
    text = path.read_text(encoding="utf-8")

    assert "RuntimeExportsProvider" in text
    assert "boot.runtime_exports_provider" not in text
