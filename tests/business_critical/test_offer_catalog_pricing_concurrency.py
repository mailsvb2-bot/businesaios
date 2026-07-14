from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from config.yaml_loader_shared import load_yaml
from runtime._internal.effects_domains.admin_pricing import (
    prepare_offer_price_update,
)


def _write_catalog(
    path: Path,
    *,
    price: int,
    version: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "catalog_id": "business-a:crm-pro:test",
                "pricing_version": version,
                "offers": [
                    {
                        "offer_id": "crm-pro-monthly",
                        "base_price_rub": int(price),
                        "rules": {},
                        "variants": {
                            "a": {
                                "title": "CRM Pro",
                                "body": "Business CRM plan",
                            }
                        },
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _prepare(
    path: Path,
    *,
    price: int,
    version: str,
    lock_timeout_s: float = 0.2,
):
    return prepare_offer_price_update(
        tenant_id="business-a",
        product_id="crm-pro",
        environment="test",
        offer_id="crm-pro-monthly",
        new_price=price,
        pricing_version=version,
        catalog_path=path,
        lock_timeout_s=lock_timeout_s,
    )


@pytest.mark.lock
def test_catalog_transaction_lock_is_held_until_finalize(
    tmp_path: Path,
) -> None:
    path = tmp_path / "business-a" / "crm-pro" / "test.yaml"
    _write_catalog(path, price=100, version="version-1")
    first = _prepare(path, price=200, version="version-2")
    try:
        with pytest.raises(
            RuntimeError,
            match="CATALOG_MUTATION_LOCK_TIMEOUT",
        ):
            _prepare(
                path,
                price=300,
                version="version-3",
                lock_timeout_s=0.05,
            )
    finally:
        first.finalize()

    second = _prepare(path, price=300, version="version-3")
    second.finalize()


@pytest.mark.lock
def test_apply_rejects_out_of_band_catalog_change_without_lost_update(
    tmp_path: Path,
) -> None:
    path = tmp_path / "business-a" / "crm-pro" / "test.yaml"
    _write_catalog(path, price=100, version="version-1")
    transaction = _prepare(path, price=200, version="version-2")
    _write_catalog(path, price=777, version="external-version")
    try:
        with pytest.raises(
            RuntimeError,
            match="PRICING_CONCURRENT_MODIFICATION",
        ):
            transaction.apply()
    finally:
        transaction.finalize()

    catalog = load_yaml(path, allow_empty=False, cache=False)
    assert catalog["pricing_version"] == "external-version"
    assert catalog["offers"][0]["base_price_rub"] == 777


@pytest.mark.lock
def test_rollback_never_overwrites_newer_catalog_revision(
    tmp_path: Path,
) -> None:
    path = tmp_path / "business-a" / "crm-pro" / "test.yaml"
    _write_catalog(path, price=100, version="version-1")
    transaction = _prepare(path, price=200, version="version-2")
    transaction.apply()
    _write_catalog(path, price=777, version="external-version")
    try:
        with pytest.raises(
            RuntimeError,
            match="PRICING_ROLLBACK_CONFLICT",
        ):
            transaction.rollback()
    finally:
        transaction.finalize()

    catalog = load_yaml(path, allow_empty=False, cache=False)
    assert catalog["pricing_version"] == "external-version"
    assert catalog["offers"][0]["base_price_rub"] == 777
