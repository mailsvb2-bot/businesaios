from pathlib import Path


def test_governed_autonomy_boot_does_not_build_runtime_directly() -> None:
    text = Path("infra/governed_autonomy_boot.py").read_text(encoding="utf-8")

    assert "build_runtime(" not in text
    assert "boot_application(" not in text
    assert "RuntimeRegistry" not in text
