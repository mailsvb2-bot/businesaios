from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    dtype: str
    group: str
    desc: str
