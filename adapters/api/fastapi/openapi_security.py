from __future__ import annotations

from typing import Any


CANON_API_OPENAPI_SECURITY = True
CANON_API_FINAL_OWNER = True


API_KEY_SCHEME_NAME = 'ApiKeyAuth'
BEARER_SCHEME_NAME = 'BearerAuth'
REQUEST_SIGNATURE_SCHEME_NAME = 'RequestSignatureHeaders'


def security_schemes() -> dict[str, Any]:
    return {
        API_KEY_SCHEME_NAME: {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-Key',
            'description': 'Tenant-bound API key for server-to-server access.',
        },
        BEARER_SCHEME_NAME: {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': 'JWT bearer token.',
        },
        REQUEST_SIGNATURE_SCHEME_NAME: {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-Signature',
            'description': 'Detached request signature. Companion headers: X-Signature-Key-Id, X-Signature-Timestamp, X-Content-Digest, X-Nonce.',
        },
    }


def attach_security_schema(app: Any) -> Any:
    original_openapi = app.openapi

    def _custom_openapi() -> dict[str, Any]:
        cached = getattr(app, 'openapi_schema', None)
        if cached is not None:
            return cached
        schema = original_openapi()
        components = schema.setdefault('components', {})
        components['securitySchemes'] = {
            **components.get('securitySchemes', {}),
            **security_schemes(),
        }
        app.openapi_schema = schema
        return schema

    app.openapi = _custom_openapi
    return app


__all__ = [
    'API_KEY_SCHEME_NAME',
    'BEARER_SCHEME_NAME',
    'CANON_API_OPENAPI_SECURITY',
    'REQUEST_SIGNATURE_SCHEME_NAME',
    'attach_security_schema',
    'security_schemes',
]
