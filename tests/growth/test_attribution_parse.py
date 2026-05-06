from core.growth.attribution import parse_utm_from_args


def test_parse_utm_and_click_ids_ampersand():
    a = parse_utm_from_args("utm_source=meta&utm_medium=paid&utm_campaign=t1:c1&utm_content=a1:ad9&gclid=G123")
    assert a.source == "meta"
    assert a.medium == "paid"
    assert a.campaign == "t1:c1"
    assert a.content == "a1:ad9"
    assert a.click_id == "G123"


def test_parse_utm_and_click_ids_semicolon():
    a = parse_utm_from_args("utm_source=yandex;utm_campaign=camp;yclid=Y999")
    assert a.source == "yandex"
    assert a.campaign == "camp"
    assert a.click_id == "Y999"


def test_parse_optional_ads_ids():
    a = parse_utm_from_args("utm_source=tg&utm_campaign=c&platform=telegram_ads&campaign_id=42&ad_id=77&impression_id=I1")
    assert a.platform == "telegram_ads"
    assert a.campaign_id == "42"
    assert a.ad_id == "77"
    assert a.impression_id == "I1"
