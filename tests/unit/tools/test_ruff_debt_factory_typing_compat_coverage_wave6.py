from __future__ import annotations

import runpy

from tools import ruff_debt_factory_typing_compat as compat


def test_ruff_debt_factory_typing_compat_reexports_main() -> None:
    assert callable(compat.main)
    assert compat.__all__ == ["main"]


def test_ruff_debt_factory_typing_compat_script_entrypoint(monkeypatch) -> None:
    calls: list[str] = []

    def fake_main() -> int:
        calls.append("called")
        return 17

    monkeypatch.setattr(
        "scripts.maintenance.ruff_debt_factory_typing_compat.main",
        fake_main,
    )

    try:
        runpy.run_module("tools.ruff_debt_factory_typing_compat", run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 17
    else:
        raise AssertionError("expected SystemExit from script entrypoint")

    assert calls == ["called"]
