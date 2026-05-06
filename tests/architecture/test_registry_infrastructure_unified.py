from pathlib import Path

from shared.registry import (
    ActionRegistry,
    ActionRunnerRegistry,
    ConnectorRegistry,
    ExperimentRegistry,
    ModelRegistry,
    PolicyRegistry,
    TemplateRegistry,
    InputRegistry,
    OpportunityRegistry,
    ServiceRegistry,
    ComponentRegistry,
)


def test_all_registries_have_namespaced_base():
    registries = [
        ServiceRegistry(),
        ComponentRegistry(),
        ActionRunnerRegistry(),
        ConnectorRegistry(),
        ExperimentRegistry(),
        ModelRegistry(),
        PolicyRegistry(),
        TemplateRegistry(),
        ActionRegistry(),
        OpportunityRegistry(),
        InputRegistry(),
    ]
    namespaces = {registry.namespace for registry in registries}
    assert len(namespaces) == len(registries)



def test_registry_alias_modules_removed() -> None:
    for relpath in (
        "registry/action_runner_registry.py",
        "registry/connector_registry.py",
        "registry/demand_source_registry.py",
        "registry/experiment_registry.py",
        "registry/intent_detector_registry.py",
        "registry/lead_delivery_registry.py",
        "registry/model_registry.py",
        "registry/policy_registry.py",
        "registry/template_registry.py",
    ):
        assert not Path(relpath).exists()
