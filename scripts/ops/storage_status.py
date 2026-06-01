from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from runtime.canonical_e2e_smoke import run_canonical_e2e_smoke
from runtime.wiring import resolve_storage_config, storage_control_plane_status, storage_live_smoke_status

"""Server-side storage readiness/live-smoke CLI.

Usage on the server:
    python -m scripts.ops.storage_status --env-file /opt/businesaios/.env
    python -m scripts.ops.storage_status --env-file /opt/businesaios/.env --live
    python -m scripts.ops.storage_status --env-file /opt/businesaios/.env --e2e

Default mode is safe/read-only and does not open database connections. The
--live and --e2e flags intentionally open configured durable stores and can
initialize schemas, so they must be used only as explicit ops gates.
"""


try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dependency is in requirements.lock.txt; kept defensive for bootstrap diagnostics.
    load_dotenv = None  # type: ignore[assignment]



def _load_env_file(path: str | None) -> None:
    if not path:
        return
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"ENV_FILE_NOT_FOUND:{env_path}")
    if load_dotenv is None:
        raise RuntimeError("PYTHON_DOTENV_NOT_AVAILABLE")
    load_dotenv(env_path, override=False)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        lowered = value.lower()
        if "postgresql://" in lowered or "postgres://" in lowered:
            return "<redacted-postgres-dsn>"
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BusinesAIOS storage readiness/live-smoke status")
    parser.add_argument("--env-file", default=os.environ.get("BUSINESAIOS_ENV_FILE"), help="Path to .env file, for example /opt/businesaios/.env")
    parser.add_argument("--base-dir", default=os.environ.get("BUSINESAIOS_DATA_DIR", "data/runtime"), help="Runtime data dir used by sqlite/dev stores")
    parser.add_argument("--live", action="store_true", help="Run explicit live smoke through canonical durable stores")
    parser.add_argument("--e2e", action="store_true", help="Run explicit canonical decision/execution/evidence/archive smoke")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.live and args.e2e:
            raise ValueError("CHOOSE_ONLY_ONE_OF_LIVE_OR_E2E")
        _load_env_file(args.env_file)
        storage = resolve_storage_config()
        if args.e2e:
            payload = run_canonical_e2e_smoke(storage, base_dir=str(args.base_dir))
        elif args.live:
            payload = storage_live_smoke_status(storage, base_dir=str(args.base_dir))
        else:
            payload = storage_control_plane_status(storage)
        print(json.dumps(_redact(payload), ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None))
        if args.live or args.e2e:
            return 0 if bool(payload.get("ok")) else 2
        return 0 if payload.get("status") == "ready" else 1
    except Exception as exc:
        error = {
            "surface": "scripts.ops.storage_status",
            "ok": False,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        print(json.dumps(_redact(error), ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
