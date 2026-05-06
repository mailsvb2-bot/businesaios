from app.web.pages.inference_runtime_admin import InferenceRuntimeAdminPage


def test_inference_runtime_admin_page_builds_all_panels():
    page = InferenceRuntimeAdminPage()
    payload = page.build(
        {
            'tenant_id': 'tenant-a',
            'headroom_usd': 100.0,
            'burn_rate_usd_per_hour': 12.5,
            'provider_mix': (
                {'provider_name': 'local_gpu_provider', 'traffic_share': 0.7, 'tier': 'local_gpu'},
                {'provider_name': 'cpu_fallback_provider', 'traffic_share': 0.3, 'tier': 'cpu_fallback'},
            ),
            'verification_summary': {
                'accepted_count': 3,
                'rejected_count': 1,
                'top_reasons': ({'reason': 'accepted', 'count': 3}, {'reason': 'schema_error', 'count': 1}),
            },
            'recent_escalations': (
                {'from_tier': 'cpu_fallback', 'to_tier': 'local_gpu', 'reason': 'pressure', 'ts': 1.0},
            ),
            'frozen': False,
            'active_tier': 'local_gpu',
        }
    )
    assert payload['title'] == 'Inference Runtime Admin'
    assert payload['budget']['kind'] == 'capacity_budget_panel'
    assert payload['provider_mix']['kind'] == 'provider_mix_panel'
    assert payload['verification']['kind'] == 'inference_verification_panel'
    assert payload['escalation_history']['kind'] == 'escalation_history_panel'
    assert payload['manual_override']['kind'] == 'manual_capacity_override_panel'
