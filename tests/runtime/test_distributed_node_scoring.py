from runtime.inference.distributed import (
    DistributedInferenceNode,
    DistributedInferenceNodeAttestation,
    DistributedInferenceNodeAttestationPolicy,
    DistributedInferenceNodeHealthScoring,
    DistributedInferenceNodeResultConsensus,
)
from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_provider_contract import InferenceResponse


def test_distributed_node_health_scoring_prefers_healthy_trusted_node():
    scoring = DistributedInferenceNodeHealthScoring()
    strong = DistributedInferenceNode('n1', 'eu', 0.9, 0.8, True)
    weak = DistributedInferenceNode('n2', 'eu', 0.5, 0.4, True)
    assert scoring.score(strong) > scoring.score(weak)


def test_distributed_node_attestation_policy_requires_evidence():
    policy = DistributedInferenceNodeAttestationPolicy()
    assert policy.allows(DistributedInferenceNodeAttestation('n1', True, 'ok')) is True
    assert policy.allows(DistributedInferenceNodeAttestation('n2', False, '')) is False


def test_distributed_node_consensus_accepts_matching_prefix():
    consensus = DistributedInferenceNodeResultConsensus()
    left = InferenceResponse('r1','p',InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK,'hello world',1,1,10,0.1,{})
    right = InferenceResponse('r2','p',InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK,'hello world again',1,1,11,0.1,{})
    assert consensus.agrees(left, right) is True
