from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _iter_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        if any(part in {".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"} for part in p.parts):
            continue
        yield p


def _scan_file_for_forbidden_imports(path: Path, forbidden_tokens: list[str]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return hits

    for i, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if not (s.startswith("import ") or s.startswith("from ")):
            continue
        for token in forbidden_tokens:
            if token in s:
                hits.append((i, s))
                break
    return hits


def test_core_has_no_direct_ads_provider_imports() -> None:
    """Canon rule: core/* must not import provider implementations directly."""

    allow_raw = os.getenv("ALLOW_FORBIDDEN_IMPORTS", "").strip().lower()
    if allow_raw in {"1", "true", "yes"}:
        return

    root = _repo_root()
    core_dir = root / "core"
    assert core_dir.exists(), "core/ directory not found"

    forbidden = [
        "interfaces.ads",
        "interfaces/ads",
        "connectors.platform.ads",
        "runtime/platform/ads",
        "telegram_ads_connector",
        "yandex_direct_connector",
        "meta_connector",
        "vk_connector",
        ".connectors",
        "connectors.",
    ]

    hits = []
    for f in _iter_py_files(core_dir):
        for (lineno, line) in _scan_file_for_forbidden_imports(f, forbidden):
            hits.append((str(f.relative_to(root)), lineno, line))

    if hits:
        msg_lines = ["Forbidden direct provider imports found in core/:", ""]
        for rel, lineno, line in hits[:50]:
            msg_lines.append(f"- {rel}:{lineno}: {line}")
        if len(hits) > 50:
            msg_lines.append(f"... and {len(hits)-50} more")
        msg_lines.append("")
        msg_lines.append("Fix: route through core.ads.AdsService and LLMAgent/provider_registry only.")
        raise AssertionError("\n".join(msg_lines))


def test_growth_ads_must_not_import_runtime_platform_or_interfaces() -> None:
    """Stricter subset: core/growth/ads/* must be clean."""

    root = _repo_root()
    target = root / "core" / "growth" / "ads"
    if not target.exists():
        return

    forbidden = ["interfaces.ads", "interfaces/ads", "connectors.platform.ads", "runtime/platform/ads"]

    hits = []
    for f in _iter_py_files(target):
        for (lineno, line) in _scan_file_for_forbidden_imports(f, forbidden):
            hits.append((str(f.relative_to(root)), lineno, line))

    if hits:
        msg_lines = ["Forbidden imports in core/growth/ads/:", ""]
        for rel, lineno, line in hits[:50]:
            msg_lines.append(f"- {rel}:{lineno}: {line}")
        if len(hits) > 50:
            msg_lines.append(f"... and {len(hits)-50} more")
        msg_lines.append("")
        msg_lines.append("Fix: growth/ads must call system.ads (AdsService) and system.marketing_llm (LLMAgent) only.")
        raise AssertionError("\n".join(msg_lines))
