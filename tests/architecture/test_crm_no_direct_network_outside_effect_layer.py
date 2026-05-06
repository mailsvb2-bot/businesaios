from pathlib import Path


FORBIDDEN = ('requests.', 'httpx.', 'aiohttp.', 'urllib.request', 'socket.')


def test_crm_contour_does_not_perform_raw_network_io():
    violations: list[str] = []
    for path in Path('crm').rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        for token in FORBIDDEN:
            if token in text:
                violations.append(f"{path}: {token}")
    assert not violations, '\n'.join(violations)
