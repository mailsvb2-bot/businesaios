from interfaces.ads.google_ads_connector import GoogleAdsConnector


def test_google_ads_connector_is_explicit_stub():
    result = GoogleAdsConnector().execute('launch_campaign', {})
    assert result.ok is False
    assert result.code == 'not_configured'
    assert result.payload['configured'] is False
