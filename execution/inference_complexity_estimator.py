from __future__ import annotations

from execution.inference_capacity_contract import InferenceCapacityRequirement
from execution.inference_workload_contract import InferenceWorkloadDescriptor


CANON_INFERENCE_COMPLEXITY_ESTIMATOR = True


class InferenceComplexityEstimator:
    def estimate(self, workload: InferenceWorkloadDescriptor) -> InferenceCapacityRequirement:
        return InferenceCapacityRequirement(
            required_context_tokens=workload.context_tokens,
            required_output_tokens=workload.expected_output_tokens,
            required_parallelism=2 if workload.batch_items > 16 else 1,
            required_batch_items=workload.batch_items,
            multimodal=workload.multimodal,
            latency_sensitive=str(workload.metadata.get('latency_sensitive') or '').strip().lower() in {'1', 'true', 'yes', 'on'},
        )
