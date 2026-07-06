"""DEPRECATED bridge: retention offer catalog.

Historically, v13 owned offer definitions under retention.config.* which caused
cyclic import pressure once offers/catalogs started depending on retention.

Canonical ownership is now in the offers layer:
  core.offers.catalogs.retention_catalog

We keep this module ONLY to avoid breaking older imports.
It must stay *lazy* and must not import OfferEngine/registries at import-time.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableMapping
from typing import Any


def _load_offers() -> dict[str, Any]:
    # Lazy import to avoid cycles.
    from core.offers.catalogs.retention_catalog import OFFERS

    # Return a plain dict (stable snapshot).
    return dict(OFFERS)


class _LazyOffersProxy(MutableMapping[str, Any]):
    _loaded: dict[str, Any] | None = None

    def _ensure(self) -> dict[str, Any]:
        if self._loaded is None:
            self._loaded = _load_offers()
        return self._loaded

    def __getitem__(self, k: str) -> Any:
        return self._ensure()[k]

    def __setitem__(self, k: str, v: Any) -> None:
        self._ensure()[k] = v

    def __delitem__(self, k: str) -> None:
        del self._ensure()[k]

    def __iter__(self) -> Iterator[str]:
        return iter(self._ensure())

    def __len__(self) -> int:
        return len(self._ensure())

    # dict-like helpers used across the codebase
    def get(self, k: str, default: Any = None) -> Any:  # type: ignore[override]
        return self._ensure().get(k, default)

    def keys(self) -> Iterable[str]:
        return self._ensure().keys()

    def items(self):
        return self._ensure().items()

    def values(self):
        return self._ensure().values()


# Backward-compat name
OFFERS: MutableMapping[str, Any] = _LazyOffersProxy()
