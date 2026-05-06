from application.business_autonomy.integration_capability_catalog import (
    capability_map,
    list_integration_capability_payloads,
    summarize_integration_capabilities,
)


def test_capability_catalog_exposes_honest_statuses():
    capabilities = capability_map()

    assert capabilities['interaction.telegram'].status.value == 'partial'
    assert capabilities['interaction.telegram'].connectable is True
    assert capabilities['acquisition.telegram_ads'].roadmap_only is True
    assert capabilities['acquisition.meta_ads'].connectable is False
    assert capabilities['acquisition.google_ads'].requires_budget_guard is True


def test_capability_payload_blocks_roadmap_as_connectable():
    rows = list_integration_capability_payloads(include_roadmap=True)
    by_id = {row['id']: row for row in rows}

    assert by_id['acquisition.meta_ads']['connectable'] is False
    assert by_id['acquisition.meta_ads']['roadmap_only'] is True
    assert by_id['interaction.email']['connectable'] is True
    assert by_id['interaction.email']['requires_consent'] is True


def test_capability_summary_counts_are_consistent():
    rows = list_integration_capability_payloads(include_roadmap=True)
    summary = summarize_integration_capabilities()

    assert summary['total'] == len(rows)
    assert summary['connectable'] + summary['roadmap_only'] == summary['total']
    assert summary['by_surface']['acquisition'] > 0
    assert summary['by_surface']['interaction'] > 0
