from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping

CANON_CI_HTTP_PROBE_IO = True


def fetch_text(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 10.0,
) -> tuple[int, str]:
    cmd = [
        "curl",
        "-sS",
        "-L",
        "-X",
        str(method or "GET").upper(),
        "--max-time",
        str(float(timeout)),
        "-w",
        "\n%{http_code}",
    ]
    for key, value in dict(headers or {}).items():
        cmd.extend(["-H", f"{str(key)}: {str(value)}"])
    if body is not None:
        cmd.extend(["--data-binary", "@-"])
    cmd.append(str(url))

    proc = subprocess.run(
        cmd,
        input=body,
        capture_output=True,
        check=False,
    )
    output = proc.stdout.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        error = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"HTTP_PROBE_FAILED:curl_exit_{proc.returncode}:{error}")

    text, _, status_text = output.rpartition("\n")
    try:
        status = int(status_text.strip())
    except ValueError as exc:
        raise RuntimeError(f"HTTP_PROBE_FAILED:invalid_status:{status_text!r}") from exc
    return status, text


def fetch_json(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    payload: Mapping[str, object] | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict]:
    body = None
    final_headers = {str(k): str(v) for k, v in dict(headers or {}).items()}
    if payload is not None:
        body = json.dumps(dict(payload), sort_keys=True).encode("utf-8")
        final_headers.setdefault("content-type", "application/json")
    status, text = fetch_text(url, method=method, headers=final_headers, body=body, timeout=timeout)
    return status, json.loads(text or "{}")


__all__ = ["CANON_CI_HTTP_PROBE_IO", "fetch_json", "fetch_text"]
