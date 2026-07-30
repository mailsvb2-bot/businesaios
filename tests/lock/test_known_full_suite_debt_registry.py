from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEBT_FILE = ROOT / "tests" / "known_full_suite_debt.txt"
ROOT_CONFTEST = ROOT / "conftest.py"
QUARANTINE_MARKERS = (
    "BUSINESAIOS_RUN_KNOWN_FULL_SUITE_DEBT",
    "known full-suite contract debt quarantined",
    "known_full_suite_debt.txt",
)


def test_known_full_suite_debt_registry_is_retired() -> None:
    assert not DEBT_FILE.exists()
    assert not ROOT_CONFTEST.exists()


def test_complete_tree_cannot_restore_known_debt_quarantine() -> None:
    inspected = [
        ROOT / "tests" / "conftest.py",
        ROOT / ".github" / "workflows" / "ci.yml",
        ROOT / ".github" / "workflows" / "full-ci.yml",
        ROOT / ".github" / "workflows" / "ci-full.yml",
    ]
    offenders: list[str] = []
    for path in inspected:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in QUARANTINE_MARKERS:
            if marker in text:
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{marker}")
    assert offenders == [], (
        "Known full-suite quarantine must not return: " + ", ".join(offenders)
    )

def test_full_ci_resets_tool_caches_before_literal_pytest() -> None:
    workflow = ROOT / ".github" / "workflows" / "full-ci.yml"
    text = workflow.read_text(encoding="utf-8")
    cleanup_marker = "- name: Reset mutable tool caches before literal pytest"
    literal_marker = "- name: Run documented complete pytest tree"

    assert cleanup_marker in text
    assert literal_marker in text
    cleanup_start = text.index(cleanup_marker)
    literal_start = text.index(literal_marker)
    assert cleanup_start < literal_start

    cleanup_block = text[cleanup_start:literal_start]
    for cache_dir in (".ruff_cache", ".pytest_cache", ".mypy_cache"):
        assert cache_dir in cleanup_block
    assert "artifacts/ci" not in cleanup_block

