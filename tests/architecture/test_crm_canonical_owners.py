from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_OWNERS = {
    ROOT / "crm/crm_connector_contract.py",
    ROOT / "crm/registry/crm_provider_registry.py",
    ROOT / "crm/state/crm_world_state_adapter.py",
}


def test_canonical_owner_files_exist() -> None:
    for path in EXPECTED_OWNERS:
        assert path.exists(), str(path.relative_to(ROOT))
