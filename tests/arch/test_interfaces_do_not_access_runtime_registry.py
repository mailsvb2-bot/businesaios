from __future__ import annotations

from pathlib import Path


def test_interfaces_do_not_access_runtime_registry() -> None:
    violations: list[str] = []

    for root in (Path("interfaces/api"), Path("interfaces/telegram")):
        if not root.exists():
            continue

        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")

            forbidden_fragments = (
                "registry.get(",
                "build_runtime(",
                "RuntimeRegistry",
                "ReadOnlyRuntimeRegistry",
                "RuntimeCapabilityAccess",
            )

            for fragment in forbidden_fragments:
                if fragment in text:
                    violations.append(
                        f"{path.as_posix()} contains forbidden runtime access fragment '{fragment}'"
                    )

    assert not violations, "\n".join(violations)


from boot.app_boot import boot_application
from interfaces.api.runtime_api_adapter import RuntimeApiAdapter
from interfaces.telegram.runtime_telegram_adapter import RuntimeTelegramAdapter


class SomeAction:
    pass


booted = boot_application()

api_adapter = RuntimeApiAdapter(
    application_service=booted.decision_application,
)
telegram_adapter = RuntimeTelegramAdapter(
    application_service=booted.decision_application,
)

result = api_adapter.handle_action(SomeAction())
print(result)

health = api_adapter.health()
print(health)
