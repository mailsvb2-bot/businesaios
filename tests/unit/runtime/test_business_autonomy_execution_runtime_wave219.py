from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.execution_support import build_execution_runtime, ensure_business_route
from runtime.execution.distributed_execution_plane import QueueSlice
from runtime.execution.region_ownership_plane import StaleReaderError


def test_execution_runtime_builds_plan_and_region_failover(tmp_path) -> None:
    docs = FileDistributedDocumentStore(tmp_path / 'docs')
    route_state = FileRegionRouteState(docs)
    route = ensure_business_route(
        route_state=route_state,
        tenant_id='tenant-demo',
        business_id='biz-1',
        primary_region='eu-west-1',
        failover_region='us-east-1',
    )
    runtime = build_execution_runtime(route_state=route_state)
    plan = runtime.planner.build_plan(
        queue_name='business-autonomy-critical',
        tenant_id='tenant-demo',
        routing_key='biz-1',
        slices=(QueueSlice(shard_id=0, depth=10, oldest_age_seconds=2, hot_partition=True),),
        desired_claims=12,
    )
    assert plan.claim_limit > 0
    assert plan.backpressure_delay_seconds >= 0
    decision = runtime.region_plane.failover(
        tenant_id='tenant-demo',
        business_id='biz-1',
        expected_epoch=route.routing_epoch,
        reason='test',
    )
    assert decision.accepted is True
    current = runtime.region_plane.read_current_route(tenant_id='tenant-demo', business_id='biz-1')
    assert current.primary_region == 'us-east-1'
    try:
        runtime.region_plane.read_current_route(tenant_id='tenant-demo', business_id='biz-1', observed_epoch=0)
    except StaleReaderError:
        pass
    else:
        raise AssertionError('expected stale-reader protection to trigger')
