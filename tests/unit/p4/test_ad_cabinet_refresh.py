from datetime import UTC, datetime

import pytest

from application.business_flows import ad_spend_guard as sg


def test_ad_cabinet_readback_and_cross_business_isolation():
    now = datetime(2026, 11, 18, tzinfo=UTC)
    rows = sg.cabinet_rows({"campaigns": [
        {"campaign_id": "123", "name": "Кампания", "state": "ON", "status": "ACCEPTED"}]})
    history = [sg.cabinet_fact(business_id="b1", at=now, rows=rows)]
    assert sg.cabinet_view(history, business_id="b1")["campaigns"] == rows
    assert sg.cabinet_view(history, business_id="b2")["status"] == "never_synced"
    history.append(sg.cabinet_fact(business_id="b1", at=now, reason="provider_dry_run"))
    assert sg.cabinet_view(history, business_id="b1")["status"] == "access_error"
    assert "отключено" in sg.cabinet_view(history, business_id="b1")["error"]


@pytest.mark.parametrize("row", [
    {}, {"campaign_id": "-1"}, {"campaign_id": "NaN"}, {"campaign_id": ""},
])
def test_ad_cabinet_rejects_unverified_identifiers(row):
    with pytest.raises(sg.ProviderReadError):
        sg.cabinet_rows({"campaigns": [row]})


def test_cabinet_never_assumes_missing_provider_data_is_zero():
    with pytest.raises(sg.ProviderReadError):
        sg.cabinet_rows({})
