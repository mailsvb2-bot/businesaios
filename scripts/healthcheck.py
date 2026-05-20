from __future__ import annotations

import json
import os


def _urllib_error():
    return __import__("urllib.error", fromlist=["_urllib_error().URLError", "_urllib_error().HTTPError"])


def _urllib_request():
    return __import__("urllib.request", fromlist=["_urllib_request().Request", "_urllib_request().urlopen"])


def _require_ready() -> bool:
    return os.getenv("HEALTHCHECK_REQUIRE_READY", "").strip().lower() in {"1", "true", "yes", "ready"}


def _is_ready_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return True
    if payload.get("ok") is False:
        return False
    if payload.get("ready") is False:
        return False
    if payload.get("status") in {"blocked", "degraded", "fail", "failed"}:
        return False
    if payload.get("runtime_wired") is False:
        return False
    return True


def main() -> None:
    url = os.getenv("HEALTH_URL", "http://localhost:8000/health").strip() or "http://localhost:8000/health"
    try:
        with _urllib_request().urlopen(url, timeout=5) as resp:
            status = int(getattr(resp, "status", 0) or 0)
            body = resp.read().decode("utf-8", errors="replace")
    except _urllib_error().HTTPError as exc:
        raise SystemExit(f"HEALTHCHECK_FAILED:{exc.code}") from exc
    except _urllib_error().URLError as exc:
        raise SystemExit(f"HEALTHCHECK_FAILED:{exc.reason}") from exc

    if status != 200:
        raise SystemExit(f"HEALTHCHECK_FAILED:{status}")

    if body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            if payload.get("ok") is False:
                raise SystemExit("HEALTHCHECK_FAILED:ok=false")
            if _require_ready() and not _is_ready_payload(payload):
                raise SystemExit("HEALTHCHECK_FAILED:not_ready")

    print("OK")


if __name__ == "__main__":
    main()
