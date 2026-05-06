from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_selected_owner_packages_install_public_api_aliases_directly() -> None:
    owner_roots = [
        "acquisition/__init__.py",
        "crm/__init__.py",
        "observability/__init__.py",
        "observability/platform/__init__.py",
        "observability/platform/observability/__init__.py",
    ]
    for rel in owner_roots:
        text = _read(rel)
        assert "install_public_api_alias(__name__)" in text, rel
        assert "public_api" in text, rel


def test_retired_explicit_public_api_modules_are_absent() -> None:
    retired = [
        "acquisition/public_api.py",
        "crm/public_api.py",
        "observability/public_api.py",
        "observability/platform/public_api.py",
        "observability/platform/observability/public_api.py",
    ]
    for rel in retired:
        assert not (ROOT / rel).exists(), rel


def test_runtime_owner_packages_install_public_api_aliases_directly() -> None:
    owner_roots = [
        "runtime/ai_ceo/__init__.py",
        "runtime/application/__init__.py",
        "runtime/behavior/__init__.py",
        "runtime/boot/__init__.py",
        "runtime/enforcement/__init__.py",
        "runtime/execution/__init__.py",
        "runtime/experiments/__init__.py",
        "runtime/explainability/__init__.py",
        "runtime/finance/__init__.py",
        "runtime/growth/__init__.py",
        "runtime/human_governance/__init__.py",
        "runtime/knowledge/__init__.py",
        "runtime/learning_loop/__init__.py",
        "runtime/llm/__init__.py",
        "runtime/product/__init__.py",
        "runtime/proofs/__init__.py",
        "runtime/queue/__init__.py",
        "runtime/ratelimit/__init__.py",
        "runtime/safety/__init__.py",
        "runtime/simulation/__init__.py",
        "runtime/state/__init__.py",
        "runtime/tenancy/__init__.py",
        "runtime/world_model/__init__.py",
        "runtime/world_state/__init__.py",
    ]
    for rel in owner_roots:
        text = _read(rel)
        assert "public_api" in text, rel
        assert ("install_public_api_alias(__name__)" in text or "install_public_api=True" in text), rel


def test_retired_runtime_public_api_pseudofiles_are_absent() -> None:
    retired = [
        "runtime/ai_ceo/public_api.py",
        "runtime/application/public_api.py",
        "runtime/behavior/public_api.py",
        "runtime/boot/public_api.py",
        "runtime/enforcement/public_api.py",
        "runtime/execution/public_api.py",
        "runtime/experiments/public_api.py",
        "runtime/explainability/public_api.py",
        "runtime/finance/public_api.py",
        "runtime/growth/public_api.py",
        "runtime/human_governance/public_api.py",
        "runtime/knowledge/public_api.py",
        "runtime/learning_loop/public_api.py",
        "runtime/llm/public_api.py",
        "runtime/product/public_api.py",
        "runtime/proofs/public_api.py",
        "runtime/queue/public_api.py",
        "runtime/ratelimit/public_api.py",
        "runtime/safety/public_api.py",
        "runtime/simulation/public_api.py",
        "runtime/state/public_api.py",
        "runtime/tenancy/public_api.py",
        "runtime/world_model/public_api.py",
        "runtime/world_state/public_api.py",
    ]
    for rel in retired:
        assert not (ROOT / rel).exists(), rel


def test_app_web_owner_packages_install_public_api_aliases_directly() -> None:
    owner_roots = [
        "app/web/__init__.py",
        "app/web/components/__init__.py",
        "app/web/pages/__init__.py",
        "app/web/components/demand/__init__.py",
        "app/web/pages/demand/__init__.py",
    ]
    for rel in owner_roots:
        text = _read(rel)
        assert "install_public_api_alias(__name__)" in text, rel
        assert "public_api" in text, rel

    removed_explicit_packages = [
        "app/web/public_api/__init__.py",
        "app/web/components/public_api/__init__.py",
        "app/web/pages/public_api/__init__.py",
        "app/web/components/demand/public_api/__init__.py",
        "app/web/pages/demand/public_api/__init__.py",
    ]
    for rel in removed_explicit_packages:
        assert not (ROOT / rel).exists(), rel


def test_boot_execution_and_core_owner_roots_install_public_api_aliases_directly() -> None:
    owner_roots = [
        "boot/__init__.py",
        "execution/__init__.py",
        "core/decision/__init__.py",
    ]
    for rel in owner_roots:
        text = _read(rel)
        assert "install_public_api_alias(__name__)" in text, rel
        assert "public_api" in text, rel

    retired = [
        "boot/public_api.py",
        "execution/public_api.py",
        "core/decision/public_api.py",
    ]
    for rel in retired:
        assert not (ROOT / rel).exists(), rel
