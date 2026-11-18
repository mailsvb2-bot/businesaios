
import pytest

from runtime.ads.connector_wiring import (
    direct_connection_key,
    direct_connection_readiness,
    per_connection_readiness_enabled,
)


def test_direct_connection_key_never_accepts_ambiguous_cross_business_scope():
    assert direct_connection_key(business_id="biz-a", account_id="client") == "biz-a::client"
    for business, account in (("", "a"), ("a::b", "c"), ("a", ""), ("a", "b::c")):
        with pytest.raises(ValueError):
            direct_connection_key(business_id=business, account_id=account)


@pytest.mark.asyncio
async def test_yandex_direct_rights_and_group_must_match_selected_business(monkeypatch):
    from interfaces.ads.registry import CONNECTORS

    monkeypatch.setenv("BAI_ADS_PER_CONNECTION_READINESS_ENABLED", "1")
    assert per_connection_readiness_enabled()
    assert CONNECTORS["yandex_direct"]["production_ready"] is False
    seen = []

    class Tokens:
        async def get(self, **kw):
            seen.append(kw["account_id"])
            return {"access_token": "test"} if kw["account_id"] == "biz-a::account-a" else None

    async def read(*, service, **kw):
        data = {
            "clients": {"result": {"Clients": [{"Login": "account-a", "Grants": [
                {"Privilege": "EDIT_CAMPAIGNS", "Value": "YES"}]}]}},
            "campaigns": {"result": {"Campaigns": [{"Id": 11, "State": "ON", "Status": "ACCEPTED"}]}},
            "adgroups": {"result": {"AdGroups": [{"Id": 22, "CampaignId": 11, "Status": "ACCEPTED"}]}},
        }
        return data[service]

    args = dict(tenant_id="tenant-a", account_id="account-a", campaign_id=11,
                ad_group_id=22, token_store=Tokens(), read=read, writes_enabled=True)
    ready = await direct_connection_readiness(business_id="biz-a", **args)
    assert ready["scope"] == {"tenant_id": "tenant-a", "business_id": "biz-a", "account_id": "account-a"}
    assert ready["ready"] is True
    assert ready["global_production_ready"] is False
    foreign = await direct_connection_readiness(business_id="biz-b", **args)
    assert not foreign["ready"] and foreign["reason"] == "business_bound_token"
    assert seen == ["biz-a::account-a", "biz-b::account-a"]


@pytest.mark.asyncio
async def test_yandex_direct_fails_closed_on_mismatched_ad_group(monkeypatch):
    monkeypatch.setenv("BAI_ADS_PER_CONNECTION_READINESS_ENABLED", "1")

    class Tokens:
        async def get(self, **_):
            return {"access_token": "test"}

    async def read(*, service, **_):
        return {
            "clients": {"result": {"Clients": [{"Grants": [
                {"Privilege": "EDIT_CAMPAIGNS", "Value": "YES"}]}]}},
            "campaigns": {"result": {"Campaigns": [{"Id": 11, "State": "ON", "Status": "ACCEPTED"}]}},
            "adgroups": {"result": {"AdGroups": [{"Id": 22, "CampaignId": 999}]}},
        }[service]

    status = await direct_connection_readiness(
        tenant_id="t", business_id="b", account_id="a", campaign_id=11,
        ad_group_id=22, token_store=Tokens(), read=read, writes_enabled=True)
    assert status["ready"] is False and status["reason"] == "ad_group_in_campaign"


def test_connection_readiness_flag_is_default_off(monkeypatch):
    monkeypatch.delenv("BAI_ADS_PER_CONNECTION_READINESS_ENABLED", raising=False)
    assert not per_connection_readiness_enabled()
