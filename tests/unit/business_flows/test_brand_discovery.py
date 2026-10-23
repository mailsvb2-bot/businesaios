import pytest

from application.business_flows import brand_discovery as bd

HTML = """<html><head><meta property="og:site_name" content="Студия Лада">
<meta name="theme-color" content="#112233"><meta name="description" content="Современный премиум сервис">
<style>:root{--brand-accent:#aabbcc;--text-main:#010203}</style>
<script type="application/ld+json">{"@type":"Organization","name":"X","logo":{"url":"/l.png"}}</script>
</head><body><img class="logo" src="/a.png"></body></html>"""


def test_suggest_extracts_brand():
    f = bd.suggest(business_id="b1", source_url="https://Example.com", html=HTML)
    assert f["step"] == "brand_suggested" and f["source_url"] == "https://example.com/"
    b = f["brand"]
    assert b["display_name"] == "Студия Лада" and b["primary_color"] == "#112233"
    assert b["accent_color"] == "#AABBCC" and b["text_color"] == "#010203"
    assert b["visual_keywords"] == ["modern", "premium"]
    assert "logo_reference_detected" in f["evidence"] and f["has_changes"]


def test_no_change_and_mismatch():
    cur = bd.Brand("b1", display_name="A")
    assert not bd.suggest(business_id="b1", source_url="http://a.ru", html="<p>x</p>", current=cur)["has_changes"]
    with pytest.raises(bd.BrandDiscoveryError):
        bd.suggest(business_id="b2", source_url="http://a.ru", html="", current=cur)


@pytest.mark.parametrize("url,code", [("ftp://a.ru", "must_be_http"), ("https://u:p@a.ru", "credentials"),
                                      ("https://a.ru:8443", "nonstandard_port"), ("", "required")])
def test_url_rules(url, code):
    with pytest.raises(bd.BrandDiscoveryError, match=code):
        bd.normalize_url(url)


def test_ssrf_and_redirects():
    pub = lambda h: ["93.184.216.34"]  # noqa: E731
    with pytest.raises(bd.BrandDiscoveryError, match="private"):
        bd.validate_public("https://x.ru", lambda h: ["10.0.0.1"])
    hops = {"https://a.ru/": (302, {"Location": "/b"}, b""),
            "https://a.ru/b": (200, {"Content-Type": "text/html; charset=utf-8"}, HTML.encode())}
    f = bd.discover(business_id="b1", website_url="https://a.ru", fetch=lambda u: hops[u], resolve=pub)
    assert f["source_url"] == "https://a.ru/b"
    with pytest.raises(bd.BrandDiscoveryError, match="html_required"):
        bd.fetch_html("https://a.ru", fetch=lambda u: (200, {"content-type": "image/png"}, b""), resolve=pub)
    with pytest.raises(bd.BrandDiscoveryError, match="redirects"):
        bd.fetch_html("https://a.ru", fetch=lambda u: (301, {"location": u}, b""), resolve=pub)
