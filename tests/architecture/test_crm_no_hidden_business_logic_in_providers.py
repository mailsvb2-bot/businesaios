from pathlib import Path


FORBIDDEN_SNIPPETS = ('DecisionCore', 'business policy', 'world_state_adapter')


def test_provider_files_stay_mapping_only():
    for path in Path('crm/providers').rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        for snippet in FORBIDDEN_SNIPPETS:
            assert snippet not in text
