from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .errors import AdsConnectorError


def _coerce_rows(*, connector_name: str, method_name: str, rows: Any) -> tuple[dict[str, Any], ...]:
    if rows is None:
        return ()
    if not isinstance(rows, Iterable) or isinstance(rows, (str, bytes, bytearray, Mapping)):
        raise AdsConnectorError(
            f"{connector_name}: {method_name} must return an iterable of mapping rows"
        )
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise AdsConnectorError(
                f"{connector_name}: {method_name} row #{idx} must be a mapping"
            )
        out.append(dict(row))
    return tuple(out)


async def read_rows(
    *,
    http: Any,
    connector_name: str,
    provider_method_name: str,
    generic_method_name: str,
    generic_platform: str,
    generic_method_label: str,
    kwargs: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    provider_method = getattr(http, provider_method_name, None)
    if callable(provider_method):
        rows = await provider_method(**kwargs)
        return _coerce_rows(
            connector_name=connector_name,
            method_name=provider_method_name,
            rows=rows,
        )

    generic_method = getattr(http, generic_method_name, None)
    if callable(generic_method):
        generic_kwargs = dict(kwargs)
        generic_kwargs['platform'] = str(generic_platform)
        rows = await generic_method(**generic_kwargs)
        return _coerce_rows(
            connector_name=connector_name,
            method_name=generic_method_name,
            rows=rows,
        )

    raise AdsConnectorError(
        f"{connector_name}: {generic_method_label} read adapter is not wired. "
        f"Provide http.{provider_method_name}(...) or http.{generic_method_name}(...)."
    )
