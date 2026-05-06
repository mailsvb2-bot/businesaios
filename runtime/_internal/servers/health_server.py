from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def start_health_server_in_thread(*, snapshot: Any, host: str, port: int) -> Any:
    """Start a local read-only HTTP server exposing /health, /ready and /panel.

    NOTE: This binds a real network port and therefore must live in runtime/_internal.
    """

    class _Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str, content_type: str) -> None:
            self.send_response(int(code))
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body.encode("utf-8", errors="ignore"))

        def do_GET(self) -> None:  # noqa: N802
            try:
                if self.path in ("/health", "/ready"):
                    payload = snapshot.collect()
                    self._send(200, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")
                    return
                if self.path == "/panel":
                    payload = snapshot.collect()
                    html = (
                        "<html><head><meta charset='utf-8'><title>Runtime Health</title></head>"
                        "<body style='font-family: ui-sans-serif, system-ui; padding: 16px;'>"
                        "<h2>Runtime Health</h2>"
                        "<pre style='background:#f6f6f6; padding:12px; border-radius:8px;'>"
                        + json.dumps(payload, ensure_ascii=False, indent=2)
                        + "</pre>"
                        "<p><a href='/health'>/health</a> • <a href='/ready'>/ready</a></p>"
                        "</body></html>"
                    )
                    self._send(200, html, "text/html; charset=utf-8")
                    return
                self._send(404, "not found", "text/plain; charset=utf-8")
            except Exception as e:
                self._send(500, f"error: {e}", "text/plain; charset=utf-8")

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    httpd = ThreadingHTTPServer((str(host), int(port)), _Handler)
    t = threading.Thread(target=httpd.serve_forever, name="health-http", daemon=True)
    t.start()
    return httpd
