from __future__ import annotations

from pathlib import Path


def test_frontend_landing_cta_is_wired_to_public_site_intake_api() -> None:
    app = Path('frontend/src/App.jsx').read_text(encoding='utf-8')

    assert 'Start CTA flow' in app
    assert 'const startCta = async () =>' in app
    assert 'postJson(endpoints.ctaStart, payload)' in app
    assert 'source: "landing"' in app
    assert 'intent: intent.trim() || DEFAULT_INTENT' in app
    assert 'window.location.assign(uiUrl)' in app
    assert 'result?.next?.ui_url' in app
    assert 'ctaStart: `${base}/public-site/cta/start`' in app
    assert 'ctaStatus: (id) => `${base}/public-site/cta/${encodeURIComponent(id)}`' in app
    assert 'const checkCtaStatus = async () =>' in app
    assert 'getJson(endpoints.ctaStatus(id))' in app


def test_frontend_landing_cta_controls_are_styled() -> None:
    styles = Path('frontend/src/styles.css').read_text(encoding='utf-8')

    assert '.hero' in styles
    assert '.cta-form' in styles
    assert 'button.primary' in styles
    assert '.success' in styles
