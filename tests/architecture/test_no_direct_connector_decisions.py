from interfaces.ads.google_ads_connector import GoogleAdsConnector


def test_connector_has_no_decide_method():
    connector = GoogleAdsConnector()
    assert not hasattr(connector, 'decide')
    result = connector.execute('launch_campaign', {})
    assert result.code == 'not_configured'
