"""MAX API trust cannot be replaced by a global TLS bypass."""
from __future__ import annotations


import pytest

from runtime.business_autonomy.provider_max_tls import max_tls_ca_file


def test_max_ca_is_opt_in_and_never_changes_other_hosts(monkeypatch):
    monkeypatch.delenv('BUSINESAIOS_MAX_CA_FILE', raising=False)
    assert max_tls_ca_file('https://platform-api2.max.ru/me') is None
    assert max_tls_ca_file('https://api.vk.com/method/messages.send') is None


def test_max_ca_fail_closed_on_foreign_host(monkeypatch, tmp_path):
    cert = tmp_path / 'root.pem'
    cert.write_text('not-a-cert')
    monkeypatch.setenv('BUSINESAIOS_MAX_CA_FILE', str(cert))
    for url in ('https://api.vk.com/method/messages.send', 'http://platform-api2.max.ru/me', 'https://platform-api2.max.ru.evil.example/me', 'https://platform-api2.max.ru:444/me'):
        with pytest.raises(ValueError, match='origin_denied'):
            max_tls_ca_file(url)


def test_max_ca_refuses_bad_certificate_even_on_correct_host(monkeypatch, tmp_path):
    cert = tmp_path / 'root.pem'
    cert.write_text('-----BEGIN CERTIFICATE-----\nYQ==\n-----END CERTIFICATE-----\n')
    monkeypatch.setenv('BUSINESAIOS_MAX_CA_FILE', str(cert))
    with pytest.raises(ValueError, match='untrusted_fingerprint'):
        max_tls_ca_file('https://platform-api2.max.ru/me')


def test_authenticated_tls_context_uses_default_trust_and_hostname_verification(monkeypatch, tmp_path):
    import runtime._internal.http_transport as transport
    observed = {}
    class DummyContext:
        def load_verify_locations(self, *, cafile):
            observed['file'] = cafile
        check_hostname = True
        verify_mode = 2
    class FakeOpener:
        def __init__(self, *handlers):
            observed['handlers'] = handlers
        def open(self, request, *, timeout):
            observed['called'] = True
            raise OSError('offline test')
    monkeypatch.setattr(transport.ssl, 'create_default_context', lambda: DummyContext())
    monkeypatch.setattr(transport._urllib_request(), 'build_opener', lambda *handlers: FakeOpener(*handlers))
    result = transport.sync_request(method='GET', url='https://platform-api2.max.ru/me', headers={'Authorization': 'test-token'}, tls_ca_file='/secure/max/root.pem')
    assert observed['file'] == '/secure/max/root.pem'
    assert any(getattr(handler, '_context', None) is not None for handler in observed['handlers'])
    assert result.error_kind == 'transport_error'
