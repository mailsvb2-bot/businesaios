from __future__ import annotations
CANON_BOOT_HEALTH_SERVER_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True


"""Minimal health endpoint server.

Design goals:
- predictable (starts only when explicitly enabled)
- dependency-free (stdlib http.server)
- no side-effects at import
- never crashes the runtime if it cannot bind

Endpoints:
- GET /health  -> 200 JSON {ok: true, ...}
- GET /ready   -> same

Env:
- TELEGRAM_HEALTH_PORT (telegram runtime)
- EVOLUTION_HEALTH_PORT (evolution worker)
- HEALTH_HOST (default 127.0.0.1)
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional

from runtime.platform.config.env_flags import env_str


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_call(fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    try:
        d = fn()
        return d if isinstance(d, dict) else {"ok": True}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__}


def _panel_html() -> bytes:
    # Read-only operator panel. No secrets, no mutable actions.
    html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\"/>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
  <title>BusinesAIOS Panel</title>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:24px;max-width:980px}
    .row{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}
    a.btn{display:inline-block;padding:10px 12px;border:1px solid #ddd;border-radius:10px;text-decoration:none;color:#111;background:#fafafa}
    a.btn:hover{background:#f2f2f2}
    pre{background:#0b1020;color:#d6e3ff;padding:14px;border-radius:12px;overflow:auto;max-height:60vh}
    .muted{color:#666;font-size:13px}
  </style>
</head>
<body>
  <h1>BusinesAIOS — operator panel</h1>
  <div class=\"muted\">Read-only. Refreshes /health every 2s. No secrets, no controls.</div>
  <div class=\"row\">
    <a class=\"btn\" href=\"/health\" target=\"_blank\">Open /health</a>
    <a class=\"btn\" href=\"/ready\" target=\"_blank\">Open /ready</a>
  </div>
  <pre id=\"out\">{}</pre>
  <script>
    async function tick(){
      try{
        const r = await fetch('/health', {cache:'no-store'});
        const t = await r.text();
        document.getElementById('out').textContent = t;
      }catch(e){
        document.getElementById('out').textContent = String(e);
      }
    }
    tick();
    setInterval(tick, 2000);
  </script>
</body>
</html>"""
    return html.encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    # injected at server construction
    _state_fn: Callable[[], Dict[str, Any]]

    def do_GET(self):  # noqa: N802
        if self.path == "/panel":
            body = _panel_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path not in ("/health", "/ready"):
            self.send_response(404)
            self.end_headers()
            return

        payload = _safe_call(self._state_fn)
        if "ts_ms" not in payload:
            payload["ts_ms"] = _now_ms()

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(200 if payload.get("ok", True) else 503)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args):
        # silence noisy stdlib server logs; use the project's logger instead.
        return


def start_health_server(
    *,
    port: int,
    state_fn: Callable[[], Dict[str, Any]],
    host: Optional[str] = None,
    name: str = "health",
) -> Optional[threading.Thread]:
    host = host or (env_str("HEALTH_HOST", "127.0.0.1") or "127.0.0.1")

    if port <= 0:
        return None

    try:
        # bind early to fail fast (but never crash the main process)
        handler = type(f"{name.title()}Handler", (_Handler,), {})
        handler._state_fn = staticmethod(state_fn)
        httpd = ThreadingHTTPServer((host, int(port)), handler)
    except Exception:
        return None

    def _serve() -> None:
        try:
            httpd.serve_forever(poll_interval=0.5)
        except Exception:
            return

    t = threading.Thread(target=_serve, name=f"{name}_server", daemon=True)
    t.start()
    return t
