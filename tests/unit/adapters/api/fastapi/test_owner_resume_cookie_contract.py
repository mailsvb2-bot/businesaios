from __future__ import annotations

from fastapi import Request, Response

from adapters.api.fastapi.public_site_routes import _OWNER_RESUME_COOKIE, _set_owner_resume_cookie


def _request(*, scheme: str) -> Request:
    return Request(
        {
            'type': 'http',
            'asgi': {'version': '3.0'},
            'http_version': '1.1',
            'method': 'GET',
            'scheme': scheme,
            'path': '/',
            'raw_path': b'/',
            'query_string': b'',
            'headers': [],
            'client': ('127.0.0.1', 12345),
            'server': ('example.test', 443 if scheme == 'https' else 80),
        }
    )


def test_owner_resume_cookie_is_http_only_strict_and_secure_on_https() -> None:
    response = Response()
    _set_owner_resume_cookie(response=response, request=_request(scheme='https'), raw_key='resume.secret')

    header = response.headers['set-cookie']
    assert header.startswith(f'{_OWNER_RESUME_COOKIE}=resume.secret;')
    assert 'HttpOnly' in header
    assert 'SameSite=strict' in header
    assert 'Secure' in header
    assert 'Path=/' in header


def test_owner_resume_cookie_allows_local_http_browser_proof_without_weakening_production_https() -> None:
    response = Response()
    _set_owner_resume_cookie(response=response, request=_request(scheme='http'), raw_key='resume.secret')

    header = response.headers['set-cookie']
    assert 'HttpOnly' in header
    assert 'SameSite=strict' in header
    assert 'Secure' not in header
