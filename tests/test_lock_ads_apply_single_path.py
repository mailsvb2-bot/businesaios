from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _py_files():
    for p in ROOT.rglob("*.py"):
        if str(p).startswith(str(ROOT / "tests")):
            continue
        yield p


def _count_occurrences(pattern: str) -> list[Path]:
    out: list[Path] = []
    rx = re.compile(pattern, re.MULTILINE)
    for p in _py_files():
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if rx.search(txt):
            out.append(p)
    return out


def test_ads_apply_execute_action_is_single_path() -> None:
    hits = _count_occurrences(r"ads_apply_execute@v1")
    rel = sorted(p.relative_to(ROOT).as_posix() for p in hits)
    assert rel == [
        "core/policies/telegram/handlers/ads_apply_flow.py",
        "runtime/boot/actions_catalog.py",
        "runtime/handlers/ads_apply_execute.py",
    ], f"Unexpected ads_apply_execute@v1 paths: {rel}"


def test_ads_apply_engine_single_definition() -> None:
    hits = _count_occurrences(r"^class\s+AdsApplyEngine\b")
    rel = sorted(p.relative_to(ROOT).as_posix() for p in hits)
    assert rel == ["core/ads/apply_engine.py"], f"Duplicate AdsApplyEngine definitions: {rel}"


def test_ads_apply_router_single_handler() -> None:
    router = ROOT / "core" / "policies" / "telegram" / "router.py"
    txt = router.read_text(encoding="utf-8", errors="ignore")
    assert "handle_ads_apply_flow" in txt, "router must call handle_ads_apply_flow"
    assert "ads_apply_execute@v1" not in txt, "router must not propose runtime action directly"
