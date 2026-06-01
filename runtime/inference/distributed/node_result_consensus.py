from __future__ import annotations

from execution.inference_provider_contract import InferenceResponse

CANON_RUNTIME_DISTRIBUTED_NODE_RESULT_CONSENSUS = True


class DistributedInferenceNodeResultConsensus:
    def agrees(self, primary: InferenceResponse, secondary: InferenceResponse) -> bool:
        left = primary.output_text.strip()
        right = secondary.output_text.strip()
        if not left or not right:
            return False
        shared_prefix_len = max(1, min(64, len(left), len(right)))
        shared = 0
        for idx in range(shared_prefix_len):
            if left[idx] != right[idx]:
                break
            shared += 1
        threshold = max(1, int(shared_prefix_len * 0.8))
        return shared >= threshold
