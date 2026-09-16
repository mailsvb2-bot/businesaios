from pathlib import Path

import pytest
import yaml

from runtime._internal.effects_actions import offer_patch_actions
from runtime._internal.effects_domains.admin_pricing import prepare_offer_price_update


class _EventLog:
    tenant_id = "business-a"

    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, **event):
        self.events.append(dict(event))
        return {"event_id": "event-1", **dict(event)}


class _Effects(offer_patch_actions.OfferPatchEffectsMixin):
    def __init__(self) -> None:
        self.event_log = _EventLog()

    def send_message(self, **kwargs):
        return {"ok": True, "kwargs": dict(kwargs)}


def _write_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "catalog_id": "business-a:crm-pro:test",
                "pricing_version": "version-1",
                "offers": [
                    {
                        "offer_id": "offer-1",
                        "base_price_rub": 100,
                        "rules": {},
                        "variants": {"a": {"title": "Old title", "body": "Body"}},
                    }
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


@pytest.mark.lock
def test_pricing_and_offer_patch_share_one_catalog_mutation_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "business-a" / "crm-pro" / "test.yaml"
    _write_catalog(catalog)
    pricing = prepare_offer_price_update(
        tenant_id="business-a",
        product_id="crm-pro",
        environment="test",
        offer_id="offer-1",
        new_price=200,
        pricing_version="version-2",
        catalog_path=catalog,
        lock_timeout_s=0.2,
    )
    monkeypatch.setenv("OFFER_CATALOG_MUTATION_LOCK_TIMEOUT_S", "0.05")
    monkeypatch.setattr(offer_patch_actions, "assert_called_from_executor", lambda: None)
    monkeypatch.setattr(
        offer_patch_actions,
        "resolve_offer_catalog",
        lambda **_kwargs: ("business-a:crm-pro:test", catalog),
    )
    effects = _Effects()
    try:
        with pytest.raises(RuntimeError, match="CATALOG_MUTATION_LOCK_TIMEOUT"):
            effects.apply_offer_patch(
                decision_id="decision-1",
                correlation_id="correlation-1",
                tenant_id="business-a",
                product="crm-pro",
                env="test",
                offer_id="offer-1",
                patch={"headline": "New title"},
                mode="apply",
            )
    finally:
        pricing.finalize()

    current = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    assert current["pricing_version"] == "version-1"
    assert current["offers"][0]["base_price_rub"] == 100
    assert current["offers"][0]["variants"]["a"]["title"] == "Old title"
    assert effects.event_log.events == []
