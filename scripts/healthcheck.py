from __future__ import annotations

def _urllib_error():
    return __import__("urllib.error", fromlist=["_urllib_error().URLError", "_urllib_error().HTTPError"])


def _urllib_request():
    return __import__("urllib.request", fromlist=["_urllib_request().Request", "_urllib_request().urlopen"])


def _urllib_parse():
    return __import__("urllib.parse", fromlist=["_urllib_parse().urlparse", "_urllib_parse().urlencode"])


import json
import os


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
            ok = payload.get("ok", True)
            if ok is False:
                raise SystemExit("HEALTHCHECK_FAILED:ok=false")
        except json.JSONDecodeError:
            pass

    print("OK")


if __name__ == "__main__":
    main()
