from pathlib import Path


def test_demand_feedback_package_is_single_owner() -> None:
    package_text = Path('demand_feedback/__init__.py').read_text(encoding='utf-8')
    assert 'register_alias_modules(' not in package_text
    assert 'install_package_submodule_alias(' not in package_text
    assert 'FeedbackSnapshotBuilder' in package_text
    assert not Path('demand_feedback/catalog.py').exists()
