from __future__ import annotations


def _build_head(*, css_href: str) -> str:
    return (
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Messaging Preferences</title>'
        f'<link rel="stylesheet" href="{css_href}">'
    )


def _build_body(*, model_endpoint: str, save_endpoint: str, js_src: str) -> str:
    return (
        '<div id="messaging-preferences-app"></div>'
        f'<script>window.__MESSAGING_PREFS__={{"modelEndpoint":"{model_endpoint}","saveEndpoint":"{save_endpoint}"}};</script>'
        f'<script src="{js_src}"></script>'
    )


def build_page(*, css_href: str, js_src: str, model_endpoint: str, save_endpoint: str) -> str:
    return (
        '<!doctype html>'
        '<html lang="en">'
        '<head>'
        f'{_build_head(css_href=css_href)}'
        '</head>'
        '<body>'
        f'{_build_body(model_endpoint=model_endpoint, save_endpoint=save_endpoint, js_src=js_src)}'
        '</body>'
        '</html>'
    )
