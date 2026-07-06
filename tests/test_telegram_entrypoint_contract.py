from __future__ import annotations

import ast
from pathlib import Path

from kernel.world_state import WorldStateV1

ROOT = Path(__file__).resolve().parents[1]


def test_telegram_entrypoint_exports_main_runtime_contract():
    import runtime.entrypoints.telegram_longpoll as ep

    assert ep.WorldStateV1 is WorldStateV1
    assert callable(ep.runtime_bootstrap)
    assert callable(ep.build_system)
    assert callable(ep.run_telegram)


def test_telegram_entrypoint_contains_no_direct_sdk_imports():
    path = ROOT / "runtime" / "entrypoints" / "telegram_longpoll.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden = {
        "aiogram",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "telegram",
        "telebot",
        "urllib",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert not any(name == item or name.startswith(item + ".") for item in forbidden)


def test_telegram_update_maps_to_single_canonical_world_state(monkeypatch):
    import runtime.entrypoints.telegram_longpoll as ep

    monkeypatch.setenv("TENANT_ID", "tenant_a")
    monkeypatch.setenv("SYSTEM_TZ", "Europe/Amsterdam")

    state = ep._world_state_from_update(
        {
            "update_id": 42,
            "message": {
                "date": 1_700_000_000,
                "text": "/start hello",
                "chat": {"id": 1001},
                "from": {"id": 2002},
            },
        }
    )

    assert isinstance(state, WorldStateV1)
    assert state.tenant_id == "tenant_a"
    assert state.user_id == "2002"
    assert state.user["telegram_chat_id"] == "1001"
    assert state.session["command"] == "/start"
    assert state.session["args"] == "hello"
    assert state.session["telegram_update_id"] == 42
    assert state.meta["transport"] == "longpoll"
