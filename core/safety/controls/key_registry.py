from __future__ import annotations

import json
import os
from dataclasses import dataclass

CANON_SAFETY_KEY_REGISTRY = True
_INSECURE_DEFAULT_KEY_ID = 'dev-insecure-default'
_INSECURE_DEFAULT_SECRET = 'businesaios-safety-local-dev-key'


@dataclass(frozen=True)
class SafetySigningKey:
    key_id: str
    secret: bytes
    active: bool = True
    insecure_fallback: bool = False


class SafetyKeyRegistry:
    def __init__(self) -> None:
        self._keys = self._load_keys()
        self._configured_current_key_id = str(os.getenv('BUSINESAIOS_SAFETY_ACTIVE_KEY_ID') or '').strip()
        self._configured_next_key_id = str(os.getenv('BUSINESAIOS_SAFETY_NEXT_KEY_ID') or '').strip()

    @property
    def current(self) -> SafetySigningKey:
        current_id = self._configured_current_key_id
        if current_id and current_id in self._keys:
            return self._keys[current_id]
        for key in self._keys.values():
            if key.active:
                return key
        return next(iter(self._keys.values()))

    @property
    def strict_mode(self) -> bool:
        raw = str(os.getenv('BUSINESAIOS_SAFETY_STRICT_KEYS') or os.getenv('BUSINESAIOS_SAFETY_BOOT_STRICT') or '').strip().lower()
        return raw in {'1', 'true', 'yes', 'on'}

    @property
    def next_key(self) -> SafetySigningKey | None:
        if self._configured_next_key_id and self._configured_next_key_id in self._keys:
            return self._keys[self._configured_next_key_id]
        return None

    def get(self, key_id: str) -> SafetySigningKey | None:
        return self._keys.get(str(key_id).strip())

    def key_ids(self) -> tuple[str, ...]:
        return tuple(self._keys.keys())

    def accepted_verification_key_ids(self) -> tuple[str, ...]:
        configured = str(os.getenv('BUSINESAIOS_SAFETY_ACCEPTED_KEY_IDS') or '').strip()
        accepted: list[str] = []
        if configured:
            accepted.extend(str(item).strip() for item in configured.split(',') if str(item).strip())
        current_id = self.current.key_id
        if current_id not in accepted:
            accepted.insert(0, current_id)
        for key_id in self._keys:
            if key_id not in accepted:
                accepted.append(key_id)
        return tuple(accepted)

    def verify_secret(self, key_id: str, signature_material: bytes, expected_hex: str, *, digestmod) -> bool:
        import hmac

        for candidate_key_id in self._candidate_key_ids(key_id):
            key = self.get(candidate_key_id)
            if key is None:
                continue
            candidate = hmac.new(key.secret, signature_material, digestmod).hexdigest()
            if hmac.compare_digest(str(expected_hex or ''), candidate):
                return True
        return False

    def has_only_insecure_fallback(self) -> bool:
        return len(self._keys) == 1 and next(iter(self._keys.values())).insecure_fallback

    def has_insecure_fallback_enabled(self) -> bool:
        return any(key.insecure_fallback for key in self._keys.values())

    def assert_secure_current(self) -> None:
        if self.strict_mode and self.current.insecure_fallback:
            raise RuntimeError('unsafe_policy_signing_key_fallback')

    def _candidate_key_ids(self, key_id: str) -> tuple[str, ...]:
        requested = str(key_id).strip()
        ordered: list[str] = []
        if requested:
            ordered.append(requested)
        for candidate in self.accepted_verification_key_ids():
            if candidate not in ordered:
                ordered.append(candidate)
        return tuple(ordered)

    def _load_keys(self) -> dict[str, SafetySigningKey]:
        configured_json = str(os.getenv('BUSINESAIOS_SAFETY_SIGNING_KEYS_JSON') or '').strip()
        keys: dict[str, SafetySigningKey] = {}
        if configured_json:
            try:
                data = json.loads(configured_json)
            except Exception:
                data = {}
            items = data.get('keys') if isinstance(data, dict) else None
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    kid = str(item.get('key_id') or '').strip()
                    secret = str(item.get('secret') or '').strip()
                    if kid and secret:
                        keys[kid] = SafetySigningKey(key_id=kid, secret=secret.encode('utf-8'), active=bool(item.get('active', True)), insecure_fallback=bool(item.get('insecure_fallback', False)))

        configured = str(os.getenv('BUSINESAIOS_SAFETY_SIGNING_KEYS') or '').strip()
        if configured:
            for raw_entry in configured.split(','):
                entry = str(raw_entry).strip()
                if not entry or ':' not in entry:
                    continue
                key_id, secret = entry.split(':', 1)
                kid = str(key_id).strip()
                if kid and secret:
                    keys[kid] = SafetySigningKey(
                        key_id=kid,
                        secret=secret.encode('utf-8'),
                        active=True,
                        insecure_fallback=False,
                    )
        single_secret = str(os.getenv('BUSINESAIOS_SAFETY_SIGNING_SECRET') or '').strip()
        single_key_id = str(os.getenv('BUSINESAIOS_SAFETY_SIGNING_KEY_ID') or 'primary').strip() or 'primary'
        if single_secret and single_key_id not in keys:
            keys[single_key_id] = SafetySigningKey(
                key_id=single_key_id,
                secret=single_secret.encode('utf-8'),
                active=True,
                insecure_fallback=False,
            )
        if not keys:
            keys[_INSECURE_DEFAULT_KEY_ID] = SafetySigningKey(
                key_id=_INSECURE_DEFAULT_KEY_ID,
                secret=_INSECURE_DEFAULT_SECRET.encode('utf-8'),
                active=True,
                insecure_fallback=True,
            )
        return keys


__all__ = ['CANON_SAFETY_KEY_REGISTRY', 'SafetyKeyRegistry', 'SafetySigningKey']
