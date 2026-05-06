from pathlib import Path


def test_app_boot_uses_runtime_integration() -> None:
    path = Path("boot/app_boot.py")
    text = path.read_text(encoding="utf-8")

    assert "RuntimeIntegration" in text
    assert "build_runtime(" not in text
