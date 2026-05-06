from __future__ import annotations

import pytest

from tests._infra.repo_scan import format_hits, scan_lines


@pytest.mark.lock
def test_lock_llm_providers_not_imported_outside_core_llm() -> None:
    """LLM lock (no bypass around guardrails/budget/retry).

    - Providers are internal (core/llm/providers/**)
    - Outside core/llm/** nobody may import providers directly.
    """

    hits = scan_lines(
        patterns={
            "import_providers_direct": r"^\s*(from\s+core\.llm\.providers\b|import\s+core\.llm\.providers\b)",
        },
        exclude_glob="core/llm/**",
        allowlist_relpaths=("tests/arch/test_lock_llm_single_entry.py",),
    )
    assert not hits, (
        "Do not import core.llm.providers outside core/llm/**.\n"
        "Use the public LLM facade (core.llm.*) only.\n" + format_hits(hits)
    )


@pytest.mark.lock
def test_lock_core_llm_is_pure_no_network_imports() -> None:
    """core/llm/** must stay pure (no network-capable imports)."""

    hits = scan_lines(
        patterns={
            "requests": r"^\s*(from\s+requests\b|import\s+requests\b)",
            "httpx": r"^\s*(from\s+httpx\b|import\s+httpx\b)",
            "aiohttp": r"^\s*(from\s+aiohttp\b|import\s+aiohttp\b)",
            "urllib": r"^\s*(from\s+urllib\b|import\s+urllib\b)",
            "socket": r"^\s*(from\s+socket\b|import\s+socket\b)",
        },
        include_glob="core/llm/**",
        allowlist_relpaths=("tests/arch/test_lock_llm_single_entry.py",),
    )
    assert not hits, "core/llm/** must not import network-capable modules.\n" + format_hits(hits)
