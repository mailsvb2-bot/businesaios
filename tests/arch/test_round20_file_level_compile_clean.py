from __future__ import annotations

from tests.arch._canon_compile_guard import file_level_compile_failures


def test_round20_file_level_compile_clean() -> None:
    failures = file_level_compile_failures()
    assert not failures, "File-level compile(...) failures found:\n- " + "\n- ".join(failures)
