from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

from canon.simplification_constitution import SIMPLIFICATION_RULES


@dataclass(frozen=True)
class CanonSimplificationManifestEntry:
    code: str
    mandatory: bool
    title: str
    operator_instruction: str


CANON_SIMPLIFICATION_MANIFEST: Final[tuple[CanonSimplificationManifestEntry, ...]] = tuple(
    CanonSimplificationManifestEntry(
        code=rule.code,
        mandatory=True,
        title=rule.title,
        operator_instruction=rule.description,
    )
    for rule in SIMPLIFICATION_RULES
)


def iter_manifest() -> Iterable[CanonSimplificationManifestEntry]:
    return CANON_SIMPLIFICATION_MANIFEST
