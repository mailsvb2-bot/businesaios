from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import shared.types as _shared_types


@dataclass(frozen=True)
class InputBundle:
    bundle_id: str = field(default_factory=lambda: _shared_types.new_id('bundle'))
    business_id: str = ''
    objective: str = 'profitable_growth'
    signals: list[dict[str, Any]] = field(default_factory=list)
    profile: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
