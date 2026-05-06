from shared.kinded_payloads import build_kinded_payload


def test_build_kinded_payload_clones_and_preserves_kind() -> None:
    payload = {'a': 1}
    result = build_kinded_payload('demo', payload)
    payload['a'] = 2
    assert result == {'kind': 'demo', 'payload': {'a': 1}}
