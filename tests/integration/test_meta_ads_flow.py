from interfaces.ads.meta_ads_connector import MetaAdsConnector


def test_meta_connector_is_stub_until_configured():
    result = MetaAdsConnector().execute('launch_campaign', {})
    assert result.code == 'not_configured'
