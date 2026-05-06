from runtime._internal.market_intelligence.http_transport import RetryPolicy
from execution.market_intelligence_sampling import AdaptiveSamplingStrategy, SamplingCandidate


def test_retry_policy_marks_429_retryable():
    policy = RetryPolicy(max_attempts=3)
    assert policy.should_retry(attempt=1, status_code=429, code='rate_limited') is True
    assert policy.should_retry(attempt=3, status_code=429, code='rate_limited') is False


def test_sampling_prefers_priority_sources():
    strategy = AdaptiveSamplingStrategy()
    selected = strategy.select([
        SamplingCandidate(provider='google', source_family='search_intelligence', priority=0.9, exploration_bias=0.0),
        SamplingCandidate(provider='reddit', source_family='professional_network', priority=0.2, exploration_bias=0.0),
    ], limit=1)
    assert selected[0].provider == 'google'
