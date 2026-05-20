from __future__ import annotations

import os
import runpy


def _env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def _health_url() -> str:
    explicit_url = os.getenv("HEALTH_URL", "").strip()
    if explicit_url:
        return explicit_url
    profile = _env("APP_PROFILE", "api").lower()
    if profile == "api":
        return f"http://127.0.0.1:{_env('API_PORT', '8000')}/readyz"
    if profile == "telegram":
        return f"http://127.0.0.1:{_env('TELEGRAM_HEALTH_PORT', '8088')}/health"
    if profile in {"worker", "evolution"}:
        return f"http://127.0.0.1:{_env('EVOLUTION_HEALTH_PORT', '8087')}/health"
    return "http://127.0.0.1:8000/readyz"


def main() -> None:
    os.environ["HEALTH_URL"] = _health_url()
    os.environ.setdefault("HEALTHCHECK_REQUIRE_READY", "1")
    runpy.run_path("scripts/healthcheck.py", run_name="__main__")


if __name__ == "__main__":
    main()
