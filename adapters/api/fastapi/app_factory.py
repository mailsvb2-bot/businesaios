from __future__ import annotations

"""FastAPI adapter owner.

The actual FastAPI construction stays delegated to the entrypoint-layer factory
for now, while the physical ownership migrates out of `interfaces/api`.
"""

from fastapi import FastAPI

from entrypoints.api.fastapi_app_factory import create_fastapi_app

CANON_FASTAPI_ADAPTER_OWNER = True
CANON_FASTAPI_ADAPTER_DELEGATES_TO_ENTRYPOINT_FACTORY = True

__all__ = ["CANON_FASTAPI_ADAPTER_OWNER", "CANON_FASTAPI_ADAPTER_DELEGATES_TO_ENTRYPOINT_FACTORY", "create_fastapi_app", "FastAPI"]
