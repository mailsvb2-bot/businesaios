from pathlib import Path


def test_fastapi_factory_uses_boot_http_surface_without_inline_runtime_assembly() -> None:
    text = Path("boot/http_boot.py").read_text(encoding="utf-8")

    assert "build_http_boot_surface" in text
    assert "build_runtime(" not in text
