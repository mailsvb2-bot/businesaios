from execution.scenario_baseline_catalog import FileScenarioBaselineCatalog


def test_scenario_baseline_catalog_roundtrip(tmp_path) -> None:
    catalog = FileScenarioBaselineCatalog(root_dir=tmp_path)
    catalog.put(scenario='Lead Gen', baseline_name='bg', source_run_id='run-1', metadata={'x': 1})
    assert catalog.exists(scenario='Lead Gen') is True
    payload = catalog.get(scenario='Lead Gen')
    assert payload['baseline_name'] == 'bg'
