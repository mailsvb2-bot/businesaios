from pathlib import Path


def test_http_boot_does_not_build_runtime_directly() -> None:
    text = Path("boot/http_boot.py").read_text(encoding="utf-8")

    assert "build_runtime(" not in text
    assert "boot_application(" in text
