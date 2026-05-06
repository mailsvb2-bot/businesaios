from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOTS = [
    "attribution/__init__.py",
    "boot/factories/__init__.py",
    "boot/registrations/__init__.py",
    "core/actions/__init__.py",
    "core/plans/__init__.py",
    "execution/effectors/__init__.py",
    "growth/seo/__init__.py",
    "marketplace/__init__.py",
    "matching/scorers/__init__.py",
    "ml/scoring/__init__.py",
    "routing/policies/__init__.py",
]


def test_package_roots_do_not_import_catalog_directly() -> None:
    for rel in PACKAGE_ROOTS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert '.catalog import' not in text, rel


def test_effector_regression_uses_package_root_owner() -> None:
    text = (ROOT / 'tests/unit/execution/test_effector_catalog_paths.py').read_text(encoding='utf-8')
    assert 'from execution.effectors import build_effector' in text
    assert 'from execution.effectors.catalog import build_effector' not in text
