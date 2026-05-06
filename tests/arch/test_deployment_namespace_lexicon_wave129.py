from __future__ import annotations

from pathlib import Path

from deployment.lexicon_contract import DEPLOYMENT_NAMESPACE_ROLES, detect_deployment_namespace

ROOT = Path(__file__).resolve().parents[2]


def test_deployment_namespace_roles_cover_current_layout() -> None:
    found = detect_deployment_namespace(ROOT)
    expected = {item.namespace for item in DEPLOYMENT_NAMESPACE_ROLES}
    assert expected.issubset(found)
    for namespace in expected:
        assert found[namespace] is True, namespace


def test_deploy_assets_do_not_become_python_owner_namespace() -> None:
    deploy_py_files = sorted((ROOT / 'deploy').rglob('*.py'))
    assert deploy_py_files == [], [str(path.relative_to(ROOT)) for path in deploy_py_files]


def test_infrastructure_assets_do_not_ship_systemd_installers() -> None:
    bad = sorted((ROOT / 'infrastructure').rglob('install.sh'))
    assert bad == [], [str(path.relative_to(ROOT)) for path in bad]
