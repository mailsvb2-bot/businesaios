from __future__ import annotations


class KnowledgeError(Exception):
    """Base knowledge-module error."""


class KnowledgeValidationError(KnowledgeError):
    """Raised when malformed knowledge input is provided."""


class KnowledgeNotFoundError(KnowledgeError):
    """Raised when a knowledge entity is absent."""


class StaleMemoryError(KnowledgeError):
    """Raised when memory is too stale to reuse safely."""


class WeakPatternError(KnowledgeError):
    """Raised when a pattern does not meet minimum confidence."""


class UnsafeReuseError(KnowledgeError):
    """Raised when knowledge reuse is unsafe for the requested task."""
