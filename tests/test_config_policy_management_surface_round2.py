from __future__ import annotations

from config import (
    CANONICAL_FLOW,
    CANONICAL_OBJECTIVE_NAME,
    ConfigSection,
    RuntimeEnvironment,
    SystemConfig,
    validate_runtime_environment,
    validate_system_config,
)



def test_system_config_normalizes_sections_and_environment() -> None:
    config = SystemConfig(environment='Production', tenant_id=' Tenant-A ')
    config.merge_section('Runtime Settings', {'workers': 4})
    config.merge_section('Policy', {'approval_required': True})

    normalized = validate_system_config(config.normalized())

    assert normalized.environment == 'prod'
    assert normalized.tenant_id == 'Tenant-A'
    assert normalized.section('runtime_settings').require('workers') == 4
    assert normalized.section('policy').require('approval_required') is True
    assert CANONICAL_OBJECTIVE_NAME == normalized.objective.name
    assert CANONICAL_FLOW[2] == 'decision'



def test_runtime_environment_validation_uses_environment_matrix() -> None:
    environment = RuntimeEnvironment(
        app_env='production',
        run_mode='headless',
        tenant_id='tenant-a',
        log_level='INFO',
        structured_logs=True,
    )
    validated = validate_runtime_environment(environment)
    assert validated.is_production is True
    assert validated.normalized_app_env == 'prod'
    assert validated.is_headless is True



def test_config_section_to_dict_rejects_empty_keys() -> None:
    section = ConfigSection(values={'good': 1})
    assert section.to_dict() == {'good': 1}
