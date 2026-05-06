"""Infrastructure observability helpers.

This namespace is for low-level observability adapters such as redaction.
The canonical surface now lives directly in the package namespace to avoid
one more thin public_api wrapper.
"""

from __future__ import annotations

from infrastructure.observability.redaction import redact_dict

CANON_INFRA_OBSERVABILITY_PUBLIC_API = True

__all__ = ["CANON_INFRA_OBSERVABILITY_PUBLIC_API", "redact_dict"]
