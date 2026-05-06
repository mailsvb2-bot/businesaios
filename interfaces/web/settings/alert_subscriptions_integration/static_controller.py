from __future__ import annotations

from pathlib import Path

from interfaces.web.common.http_response import HttpResponse
from interfaces.web.settings.common.static_asset_reader import read_text_asset


class StaticController:
    def __init__(self, *, root: Path):
        self._root = root

    def get_css(self) -> HttpResponse:
        body = read_text_asset(
            root=self._root,
            relative_path="interfaces/web/settings/alert_subscriptions/static/alert_subscriptions.css",
        )
        return HttpResponse(
            status_code=200,
            content_type="text/css; charset=utf-8",
            body=body,
        )

    def get_js(self) -> HttpResponse:
        body = read_text_asset(
            root=self._root,
            relative_path="interfaces/web/settings/alert_subscriptions/static/alert_subscriptions.js",
        )
        return HttpResponse(
            status_code=200,
            content_type="application/javascript; charset=utf-8",
            body=body,
        )
