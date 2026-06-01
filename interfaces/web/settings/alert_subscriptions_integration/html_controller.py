from __future__ import annotations

from interfaces.web.common.http_response import HttpResponse
from interfaces.web.settings.alert_subscriptions.html_page import build_page


class HtmlController:
    def get_page(
        self,
        *,
        css_href: str,
        js_src: str,
        model_endpoint: str,
        save_endpoint: str,
    ) -> HttpResponse:
        body = build_page(
            css_href=css_href,
            js_src=js_src,
            model_endpoint=model_endpoint,
            save_endpoint=save_endpoint,
        )
        return HttpResponse(
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=body,
        )
