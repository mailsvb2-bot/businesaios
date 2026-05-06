from __future__ import annotations

from typing import Any

from execution.inference_workload_contract import (
    InferenceWorkloadDescriptor,
    InferenceWorkloadKind,
)


CANON_INFERENCE_WORKLOAD_CLASSIFIER = True


class InferenceWorkloadClassifier:
    def classify(self, *, prompt: str, metadata: dict[str, Any] | None = None) -> InferenceWorkloadDescriptor:
        normalized = {str(k): v for k, v in dict(metadata or {}).items()}
        kind_raw = str(normalized.get('kind') or InferenceWorkloadKind.CHAT.value).strip()
        try:
            kind = InferenceWorkloadKind(kind_raw)
        except ValueError:
            kind = InferenceWorkloadKind.CHAT
        context_tokens = max(1, len(prompt) // 4)
        expected_output_tokens = int(normalized.get('expected_output_tokens', 512) or 512)
        batch_items = int(normalized.get('batch_items', 1) or 1)
        multimodal = str(normalized.get('multimodal', 'false')).strip().lower() in {'1', 'true', 'yes', 'on'}
        return InferenceWorkloadDescriptor(
            workload_id=str(normalized.get('workload_id') or 'generated'),
            kind=kind,
            context_tokens=context_tokens,
            expected_output_tokens=expected_output_tokens,
            batch_items=batch_items,
            multimodal=multimodal,
            tenant_id=str(normalized.get('tenant_id') or '').strip() or None,
            metadata={str(k): str(v) for k, v in normalized.items()},
        )
