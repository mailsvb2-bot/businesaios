from __future__ import annotations

from dataclasses import dataclass

CANON_CRYPTOGRAPHIC_AGILITY = True

@dataclass(frozen=True)
class CryptographicProfile:
    profile_name: str
    encryption_algorithm: str
    signature_scheme: str
    hash_algorithm: str
    key_size_bits: int


class CryptographicAgilityRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, CryptographicProfile] = {}

    def register(self, profile: CryptographicProfile) -> None:
        if not str(profile.profile_name or '').strip():
            raise ValueError('profile_name is required')
        if int(profile.key_size_bits) < 128:
            raise ValueError('key_size_bits must be >= 128')
        self._profiles[profile.profile_name] = profile

    def get(self, profile_name: str) -> CryptographicProfile:
        try:
            return self._profiles[str(profile_name)]
        except KeyError as exc:
            raise KeyError(f'unknown cryptographic profile: {profile_name}') from exc

    def list_profiles(self) -> tuple[CryptographicProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

__all__ = ['CANON_CRYPTOGRAPHIC_AGILITY', 'CryptographicAgilityRegistry', 'CryptographicProfile']
