"""Canonical checkpoint support surface with compat alias submodules."""

from __future__ import annotations

import hashlib
import hmac
import os
import pickle
import secrets
from dataclasses import dataclass
from pathlib import Path

_CHECKPOINT_MAGIC = b'BAIOSCK1'
_CHECKPOINT_SIGNING_KEY_ENV = 'BUSINESAIOS_CHECKPOINT_SIGNING_KEY'
_PROCESS_KEY = secrets.token_bytes(32)


def _checkpoint_key() -> bytes:
    key = str(os.getenv(_CHECKPOINT_SIGNING_KEY_ENV) or '').strip()
    if key:
        return key.encode('utf-8')
    environments = {str(os.getenv(name) or '').strip().lower() for name in ('APP_ENV','ENV')}
    if environments & {'prod','production','stage','staging','preprod'}:
        raise RuntimeError('checkpoint_signing_key_required')
    return _PROCESS_KEY


class CheckpointGC:
    def prune(self, directory: str, keep: int) -> list[str]:
        paths = sorted(Path(directory).glob("checkpoint_step_*.bin"))
        removed: list[str] = []
        while len(paths) > keep:
            path = paths.pop(0)
            path.unlink(missing_ok=True)
            removed.append(str(path))
        return removed

def valid_checkpoint_payload(payload: dict) -> bool:
    return "state" in payload and "step" in payload

class CheckpointLoading:
    def load(self, path: str):
        with open(path, 'rb') as file:
            raw = file.read()
        header_length = len(_CHECKPOINT_MAGIC) + hashlib.sha256().digest_size
        if len(raw) <= header_length or not raw.startswith(_CHECKPOINT_MAGIC):
            raise ValueError('checkpoint_unsigned_or_corrupt')
        signature = raw[len(_CHECKPOINT_MAGIC):header_length]
        data = raw[header_length:]
        expected = hmac.new(_checkpoint_key(), data, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError('checkpoint_signature_invalid')
        return pickle.loads(data)  # noqa: S301 - authenticated with the configured HMAC signing key

@dataclass(frozen=True)
class CheckpointMetadata:
    step: int
    metric: float
    uri: str

def checkpoint_name(step: int) -> str:
    return f"checkpoint_step_{step}.bin"

class CheckpointPolicy:
    def should_save(self, current_metric: float, best_metric: float | None) -> bool:
        return best_metric is None or current_metric < best_metric

class CheckpointPromotion:
    def promote(self, checkpoint_uri: str) -> dict[str, str]:
        return {"promoted_checkpoint": checkpoint_uri}

class CheckpointSaving:
    def save(self, path: str, payload) -> None:
        data = pickle.dumps(payload)
        signature = hmac.new(_checkpoint_key(), data, hashlib.sha256).digest()
        with open(path, 'wb') as file:
            file.write(_CHECKPOINT_MAGIC + signature + data)

class Warmstart:
    def apply(self, model, checkpoint_payload):
        return {"model": model, "checkpoint": checkpoint_payload}

class CheckpointManager:
    def __init__(self, directory: str, policy: CheckpointPolicy | None = None, saver: CheckpointSaving | None = None) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._policy = policy or CheckpointPolicy()
        self._saver = saver or CheckpointSaving()
        self._best_metric: float | None = None

    def maybe_save(self, state, metric: float):
        if not self._policy.should_save(metric, self._best_metric):
            return None
        path = self._directory / checkpoint_name(getattr(state, "step", 0))
        payload = {"state": state, "step": getattr(state, "step", 0), "metric": metric}
        self._saver.save(str(path), payload)
        self._best_metric = metric
        return CheckpointMetadata(step=getattr(state, "step", 0), metric=metric, uri=str(path))

__all__ = [
    "CheckpointGC",
    "CheckpointLoading",
    "CheckpointManager",
    "CheckpointMetadata",
    "CheckpointPolicy",
    "CheckpointPromotion",
    "CheckpointSaving",
    "Warmstart",
    "checkpoint_name",
    "valid_checkpoint_payload",
]
