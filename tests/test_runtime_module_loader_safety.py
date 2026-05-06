from __future__ import annotations

from pathlib import Path

import pytest

from runtime.handler_loader import import_module_or_file


def test_loader_raises_real_import_errors_instead_of_masking_them() -> None:
    mod = Path(__file__).resolve().parents[1] / "runtime" / "handlers" / "_loader_broken_fixture.py"
    mod.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    try:
        with pytest.raises(RuntimeError, match="boom"):
            import_module_or_file(
                module_name="runtime.handlers._loader_broken_fixture",
                file_path=mod,
                fallback_name="broken_mod_fallback",
            )
    finally:
        mod.unlink(missing_ok=True)


def test_loader_refuses_paths_outside_project_root(tmp_path: Path) -> None:
    mod = tmp_path / "elsewhere.py"
    mod.write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="outside project root"):
        import_module_or_file(
            module_name="runtime.handlers.elsewhere",
            file_path=mod,
            fallback_name="elsewhere_fallback",
        )
