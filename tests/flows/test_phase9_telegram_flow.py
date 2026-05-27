from __future__ import annotations

import importlib


def test_telegram_boot_modules_import() -> None:
    modules = [
        "runtime.bootstrap",
        "runtime.boot.env",
        "runtime.boot.mode_gate",
    ]
    for name in modules:
        module = importlib.import_module(name)
        assert module is not None

def test_telegram_token_resolution_callable() -> None:
    env = importlib.import_module("runtime.boot.env")
    resolver = getattr(env, "resolve_telegram_bot_token", None)
    assert callable(resolver)
