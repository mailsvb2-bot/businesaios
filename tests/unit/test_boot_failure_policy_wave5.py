from __future__ import annotations

import pytest

from runtime.boot.failure_policy import boot_fail_closed, raise_or_log_boot_failure


class _Core:
    def __init__(self, *, env: str = "dev", production_strict_mode: bool = False) -> None:
        self.env = env
        self.production_strict_mode = production_strict_mode


class _Settings:
    def __init__(self, *, env: str = "dev", production_strict_mode: bool = False) -> None:
        self.core = _Core(env=env, production_strict_mode=production_strict_mode)


def test_boot_fail_closed_uses_settings_strict_mode() -> None:
    assert boot_fail_closed(settings=_Settings(env="prod", production_strict_mode=True)) is True


def test_raise_or_log_boot_failure_degrades_outside_strict_mode() -> None:
    raise_or_log_boot_failure(component="ads_stack", exc=ValueError("boom"), settings=_Settings(env="dev"))


def test_raise_or_log_boot_failure_raises_in_strict_mode() -> None:
    with pytest.raises(RuntimeError, match="BOOT_COMPONENT_FAILED:ads_stack"):
        raise_or_log_boot_failure(
            component="ads_stack",
            exc=ValueError("boom"),
            settings=_Settings(env="prod", production_strict_mode=True),
        )
