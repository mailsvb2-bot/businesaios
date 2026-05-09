from __future__ import annotations

import os

from bootstrap.http_boot_surface import build_http_boot_surface


def build_app():
    surface = build_http_boot_surface()
    return surface.http_app


app = build_app()


def main() -> None:
    import uvicorn

    host = os.getenv("BUSINESAIOS_HTTP_HOST", "127.0.0.1")
    port = int(os.getenv("BUSINESAIOS_HTTP_PORT", "8090"))
    log_level = os.getenv("BUSINESAIOS_LOG_LEVEL", "info")

    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
