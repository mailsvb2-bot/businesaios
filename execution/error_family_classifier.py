from __future__ import annotations

CANON_ERROR_FAMILY_CLASSIFIER = True


def _text(value: object) -> str:
    return str(value or '').strip().lower()


class ErrorFamilyClassifier:
    def classify(self, error: object) -> str:
        token = _text(error)
        if not token:
            return 'unknown'
        if 'rate_limit' in token or '429' in token:
            return 'rate_limit'
        if 'timeout' in token or 'temporar' in token or 'network' in token or 'connection' in token:
            return 'transport'
        if 'auth' in token or 'token' in token or 'forbidden' in token or 'permission' in token:
            return 'authorization'
        if 'validation' in token or 'invalid' in token or 'schema' in token:
            return 'validation'
        return 'generic'


__all__ = ['CANON_ERROR_FAMILY_CLASSIFIER', 'ErrorFamilyClassifier']
