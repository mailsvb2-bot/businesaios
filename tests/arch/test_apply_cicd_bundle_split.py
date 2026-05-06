from __future__ import annotations

from pathlib import Path


def test_apply_cicd_bundle_script_is_thin_and_delegates_parts() -> None:
    path = Path("scripts/apply_cicd_canon_v7_project_bundle.py")
    text = path.read_text(encoding="utf-8")
    assert "canon_bundle_part_a" in text
    assert "canon_bundle_part_b" in text
    assert "canon_bundle_part_c" in text
    assert "for relative_path, content in _iter_bundle_entries():" in text
    assert sum(1 for _ in path.open(encoding="utf-8")) < 80


def test_bundle_part_modules_exist_and_are_nonempty() -> None:
    for rel in [
        "scripts/ci/canon_bundle_part_a.py",
        "scripts/ci/canon_bundle_part_b.py",
        "scripts/ci/canon_bundle_part_c.py",
    ]:
        path = Path(rel)
        assert path.exists(), rel
        assert path.read_text(encoding="utf-8").strip(), rel
