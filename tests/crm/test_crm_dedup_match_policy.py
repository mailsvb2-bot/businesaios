from crm.upsert.crm_dedup_match_policy import CrmDedupMatchPolicy


def test_dedup_policy_detects_existing_record():
    match = CrmDedupMatchPolicy().evaluate(existing_record_id='123', dedup_key='lead:x')
    assert match.matched is True
