from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from crm.crm_stage_contract import CrmStage


@dataclass(frozen=True)
class CrmPipeline:
    pipeline_key: str
    display_name: str
    stages: tuple[CrmStage, ...]
    external_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
