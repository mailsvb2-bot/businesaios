from __future__ import annotations

import re
from pathlib import Path

import product
import products

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS_IMPORT = re.compile(r"^\s*(?:from\s+products\b|import\s+products\b)", re.MULTILINE)
PRODUCT_IMPORT = re.compile(r"^\s*(?:from\s+product\b|import\s+product\b)", re.MULTILINE)

def _python_files_under(rel_dir: str) -> list[Path]:
    base = ROOT / rel_dir
    return sorted(path for path in base.rglob("*.py") if path.is_file())

def test_product_and_products_roles_and_boundaries_stay_distinct() -> None:
    product_role = (ROOT / "product" / "CANON_NAMESPACE_ROLE.md").read_text(encoding="utf-8")
    assert "runtime-facing product service surface" in product_role
    assert "second product-definition truth" in product_role

    products_role = (ROOT / "products" / "CANON_NAMESPACE_ROLE.md").read_text(encoding="utf-8")
    assert "product-definition and catalog surface" in products_role
    assert "second business-service layer" in products_role

    assert product.CANON_PRODUCT_SERVICE_NAMESPACE is True
    assert products.CANON_PRODUCTS_DEFINITION_NAMESPACE is True

    offenders = []
    for path in _python_files_under("product"):
        text = path.read_text(encoding="utf-8")
        if PRODUCTS_IMPORT.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], offenders

    offenders = []
    for path in _python_files_under("products"):
        text = path.read_text(encoding="utf-8")
        if PRODUCT_IMPORT.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], offenders
