from execution.action_catalog import classify_action_type, get_action_spec, known_action_types, normalize_action_type


def test_normalize_action_type_collapses_version_and_prefix() -> None:
    assert normalize_action_type('ACTION_EXECUTE_PLAN_V1') == 'execute_plan'


def test_catalog_provides_canonical_internal_spec() -> None:
    spec = get_action_spec('ACTION_EXECUTE_PLAN_V1')
    assert spec.action_class == 'internal_execution'
    assert spec.routable is False
    assert spec.executable is False


def test_catalog_known_actions_include_external_runner_types() -> None:
    assert 'launch_campaign' in known_action_types()
    assert classify_action_type('launch_campaign') == 'ads_write'


def test_catalog_normalizes_runtime_action_version_suffixes() -> None:
    assert normalize_action_type('send_message@v1') == 'send_message'
    assert classify_action_type('send_message@v1') == 'communications_write'
