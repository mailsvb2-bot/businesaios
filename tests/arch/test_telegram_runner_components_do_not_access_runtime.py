from pathlib import Path


def test_telegram_runner_components_do_not_access_runtime() -> None:
    for rel in (
        "interfaces/telegram/runner_components.py",
        "interfaces/telegram/runner_helpers.py",
        "interfaces/telegram/sdk_adapter.py",
        "interfaces/telegram/telegram_runner_integration.py",
    ):
        text = Path(rel).read_text(encoding="utf-8")
        forbidden = (
            "RuntimeRegistry",
            "ReadOnlyRuntimeRegistry",
            "registry.get(",
            "build_runtime(",
            "RuntimeCapabilityAccess",
        )
        for fragment in forbidden:
            assert fragment not in text
