from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


CANON_INFERENCE_WORKLOAD_CONTRACT = True


class InferenceWorkloadKind(str, Enum):
    CHAT = 'chat'
    SUMMARIZATION = 'summarization'
    EMBEDDINGS = 'embeddings'
    CLASSIFICATION = 'classification'
    SIMULATION = 'simulation'
    MULTIMODAL = 'multimodal'
    BATCH_ANALYSIS = 'batch_analysis'


class InferenceWorkloadUrgency(str, Enum):
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    CRITICAL = 'critical'


@dataclass(frozen=True)
class InferenceWorkloadDescriptor:
    workload_id: str
    kind: InferenceWorkloadKind
    context_tokens: int
    expected_output_tokens: int
    batch_items: int = 1
    urgency: InferenceWorkloadUrgency = InferenceWorkloadUrgency.NORMAL
    multimodal: bool = False
    tenant_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
