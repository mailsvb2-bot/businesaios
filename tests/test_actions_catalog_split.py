from pathlib import Path


def test_actions_catalog_split_into_groups():
    catalog = Path("core/actions/catalog.py").read_text(encoding="utf-8")
    assert "build_catalog_groups" in catalog
    assert len(catalog.splitlines()) < 50
    groups = Path("core/actions/catalog_groups.py").read_text(encoding="utf-8")
    assert "governance_catalog" in groups
    assert "payments_catalog" in groups
