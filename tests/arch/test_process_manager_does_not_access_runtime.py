from pathlib import Path


def test_process_manager_does_not_access_runtime() -> None:
    text = Path("infra/process_manager.py").read_text(encoding="utf-8")

    forbidden = (
        "RuntimeRegistry",
        "ReadOnlyRuntimeRegistry",
        "registry.get(",
        "build_runtime(",
        "RuntimeCapabilityAccess",
    )
    for fragment in forbidden:
        assert fragment not in text
