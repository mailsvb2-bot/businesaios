from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_builtin_modules_do_not_register_raw_decision_core_service_name() -> None:
    path = ROOT / "runtime" / "modules" / "builtin_modules.py"
    text = path.read_text(encoding="utf-8")
    assert 'ctx.services.setdefault("decision_core"' not in text


def test_builtin_modules_register_decision_gateway_service_name() -> None:
    path = ROOT / "runtime" / "modules" / "builtin_modules.py"
    text = path.read_text(encoding="utf-8")
    assert 'ctx.services.setdefault("decision_gateway"' in text
