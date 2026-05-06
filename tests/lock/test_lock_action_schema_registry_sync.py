from core.actions.schema_registry import build_default_registry
from runtime.boot.actions_registry import SPECS


def test_action_schema_registry_is_superset_of_runtime_actions():
    reg = build_default_registry()
    runtime_actions = {s.name for s in SPECS}
    missing = runtime_actions - reg.names()
    assert not missing, f"Missing payload schemas for actions: {sorted(missing)}"
