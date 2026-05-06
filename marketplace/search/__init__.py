from __future__ import annotations

class GeoQueryMapper:
    def map(self, text: str) -> str:
        return 'amsterdam' if 'amsterdam' in str(text).lower() else 'remote'

class IntentToCategoryMapper:
    def map(self, intent) -> str:
        return str(intent.service_type or 'general')

class QueryNormalizer:
    def normalize(self, text: str) -> str:
        return ' '.join(str(text).lower().split())

class QueryParser:
    def parse(self, text: str) -> tuple[str, ...]:
        return tuple(str(text).lower().split())

class SearchRanker:
    def rank(self, profiles: tuple[object, ...]) -> tuple[object, ...]:
        return tuple(sorted(profiles, key=lambda p: p.name))

__all__ = [
    'GeoQueryMapper',
    'IntentToCategoryMapper',
    'QueryNormalizer',
    'QueryParser',
    'SearchRanker',
]
