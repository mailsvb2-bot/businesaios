from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_registration_manifest_uses_registry_and_action_constant() -> None:
    text = (ROOT / 'runtime' / 'boot' / 'registration_manifest.py').read_text(encoding='utf-8')
    assert 'from runtime.boot.actions_registry import all_actions' in text
    assert 'from runtime.actions import ACTION_AI_CEO_PLAN_V1' in text
    assert 'ai_ceo_plan@v1' not in text


def test_registration_manifest_does_not_own_catalog_rows() -> None:
    text = (ROOT / 'runtime' / 'boot' / 'registration_manifest.py').read_text(encoding='utf-8')
    assert 'SPEC_ROWS' not in text
    assert 'INLINE_ALLOWLIST_NAMES' not in text
    assert 'handlers.register(' in text
