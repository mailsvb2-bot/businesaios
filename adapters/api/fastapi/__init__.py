from __future__ import annotations


def create_api_router(*args, **kwargs):
    from adapters.api.fastapi.router_adapter import create_api_router as _create_api_router

    return _create_api_router(*args, **kwargs)


def create_fastapi_app(*args, **kwargs):
    from adapters.api.fastapi.app_factory import create_fastapi_app as _create_fastapi_app

    return _create_fastapi_app(*args, **kwargs)


__all__ = ["create_api_router", "create_fastapi_app"]
