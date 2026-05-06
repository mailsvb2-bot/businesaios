from __future__ import annotations

import pathlib

import pytest

from tests._infra.repo_scan import format_hits, scan_lines


@pytest.mark.lock
def test_lock_telegram_worldstate_builder_is_single_path() -> None:
    """Telegram WorldState single path lock."""

    canonical = pathlib.Path("interfaces/telegram/runtime/telegram_runtime_worldstate_builder.py")
    assert canonical.exists(), f"Missing canonical builder: {canonical.as_posix()}"

    hits = scan_lines(
        patterns={
            "legacy_worldstate_import": r"^\s*(from\s+interfaces\.telegram\.worldstate_builder\b|import\s+interfaces\.telegram\.worldstate_builder\b)",
        },
        allowlist_relpaths=("tests/arch/test_lock_telegram_worldstate_single_path.py",),
    )
    assert not hits, (
        "Legacy Telegram worldstate builder imports are forbidden.\n"
        "Use interfaces/telegram/runtime/telegram_runtime_worldstate_builder.py only.\n"
        + format_hits(hits)
    )
