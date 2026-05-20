from __future__ import annotations

import asyncio
import json

from entrypoints.api.fastapi_app_factory import create_app


async def _request(path: str) -> tuple[int, dict[str, object]]:
    app = create_app()
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app({"type": "http", "method": "GET", "path": path}, receive, send)
    status = int(sent[0]["status"])
    body = json.loads(sent[1]["body"].decode("utf-8"))
    return status, body


def test_fail_closed_health_does_not_claim_runtime_ready() -> None:
    status, body = asyncio.run(_request("/health"))

    assert status == 200
    assert body["status"] == "alive"
    assert body["process_alive"] is True
    assert body["runtime_wired"] is False
    assert body["ready"] is False
    assert body["reason"] == "runtime_application_service_not_wired"


def test_fail_closed_readiness_surfaces_are_explicitly_blocked() -> None:
    for path, flag in (
        ("/readyz", "ready"),
        ("/startupz", "startup_complete"),
        ("/storagez", "storage_ready"),
        ("/executionz", "execution_ready"),
    ):
        status, body = asyncio.run(_request(path))
        assert status == 200
        assert body["status"] == "blocked"
        assert body["runtime_wired"] is False
        assert body[flag] is False
