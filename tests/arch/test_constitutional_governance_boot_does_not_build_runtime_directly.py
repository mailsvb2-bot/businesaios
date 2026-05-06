from pathlib import Path


def test_constitutional_governance_boot_does_not_build_runtime_directly() -> None:
    text = Path("infra/constitutional_governance_boot.py").read_text(encoding="utf-8")

    assert "build_runtime(" not in text
    assert "boot_application(" not in text
    assert "RuntimeRegistry" not in text
