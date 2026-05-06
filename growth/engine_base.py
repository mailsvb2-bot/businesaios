from __future__ import annotations

"""Shared helpers for Growth engine surfaces.

Keeps payload normalization and artifact emission in one place so campaign / creative /
budget engines do not each re-implement the same mini-contract glue.
"""

from typing import Mapping

from growth.engine_contract import build_artifact, normalize_payload


class GrowthEngineSurface:
    def payload(self, payload: Mapping[str, object] | None) -> dict[str, object]:
        return normalize_payload(payload)

    def artifact(self, kind: str, payload: Mapping[str, object] | None) -> dict[str, object]:
        return build_artifact(kind, payload)


__all__ = ["GrowthEngineSurface"]
