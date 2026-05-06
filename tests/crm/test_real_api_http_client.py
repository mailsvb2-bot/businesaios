from urllib.parse import parse_qs

from crm.providers.common.crm_http_client import CrmHttpClient, CrmHttpRequest


class _Response:
    def __init__(self, body: bytes = b'{}') -> None:
        self.status = 200
        self.headers = {'Content-Type': 'application/json'}
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_http_client_encodes_form_body(monkeypatch):
    captured = {}

    def fake_open(req, timeout):
        captured['data'] = req.data
        captured['headers'] = dict(req.header_items())
        captured['timeout'] = timeout
        return _Response()

    client = CrmHttpClient(base_url='https://example.test', opener=fake_open)
    client.send(
        CrmHttpRequest(
            method='POST',
            path='/oauth/token',
            form_body={'grant_type': 'authorization_code', 'code': 'abc', 'redirect_uri': 'https://x/y'},
            timeout_seconds=12.0,
        )
    )

    body = parse_qs(captured['data'].decode('utf-8'))
    assert body['grant_type'] == ['authorization_code']
    assert body['code'] == ['abc']
    assert captured['timeout'] == 12.0
    assert captured['headers']['Content-type'] == 'application/x-www-form-urlencoded'
