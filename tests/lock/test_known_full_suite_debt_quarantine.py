from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEBT_FILE = ROOT / "tests" / "known_full_suite_debt.txt"
MAX_KNOWN_DEBT = 172


def _entries() -> list[str]:
    return [
        line.strip()
        for line in DEBT_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_known_full_suite_debt_is_exact_bounded_and_auditable() -> None:
    entries = _entries()

    assert entries == sorted(entries)
    assert len(entries) == len(set(entries))
    assert len(entries) <= MAX_KNOWN_DEBT

    for node_id in entries:
        assert "::" in node_id
        assert not any(token in node_id for token in ("*", "?", "[", "]"))
        path, test_name = node_id.split("::", maxsplit=1)
        assert path.startswith("tests/")
        assert test_name.startswith("test_")
        assert (ROOT / path).is_file(), node_id


def test_known_full_suite_debt_can_only_shrink_without_explicit_lock_update() -> None:
    assert len(_entries()) <= MAX_KNOWN_DEBT
