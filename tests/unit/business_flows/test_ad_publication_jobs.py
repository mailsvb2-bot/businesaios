from application.business_flows import ad_media as am
from application.business_flows import ad_publication_jobs as aj


def sess(p=None, token=None):
    return aj.Session(p or aj.DryRunDirectProvider(), token or {"access_token": "t", "refresh_token": "r"})


def test_managed_campaign_created_disabled_once_and_reused():
    p = aj.DryRunDirectProvider()
    m, facts = aj.ensure_managed_campaign(aj.Ledger(), sess(p), business_id="b", promotion_id="pr", connection_id="c")
    led = aj.replay(facts)
    assert m.status == "ready" and led.managed[m.key].external_campaign_id == m.external_campaign_id
    m2, facts2 = aj.ensure_managed_campaign(led, sess(p), business_id="b", promotion_id="pr", connection_id="c")
    assert facts2 == [] and m2 == led.managed[m.key]
    assert [c[0] for c in p.calls] == ["find", "create_disabled"]


class Flaky(aj.DryRunDirectProvider):
    def __init__(self, err):
        super().__init__()
        self.err = err

    def create_disabled_managed_campaign(self, access_token, campaign_name):
        if self.err:
            e, self.err = self.err, None
            raise e
        return super().create_disabled_managed_campaign(access_token, campaign_name)


def test_managed_failure_uncertain_blocks_and_confirmed_failure_reclaims():
    log = []
    try:
        aj.ensure_managed_campaign(aj.Ledger(), sess(Flaky(aj.DirectError("timeout", retryable=True))),
                                   business_id="b", promotion_id="p", connection_id="c")
    except aj.DirectError as e:
        log += e.facts
    led = aj.replay(log)
    assert next(iter(led.managed.values())).status == "provisioning"
    try:
        aj.ensure_managed_campaign(led, sess(), business_id="b", promotion_id="p", connection_id="c")
        raise AssertionError
    except aj.Busy:
        pass
    led = aj.replay(log + [{"step": "ad_managed_failed", "key": next(iter(led.managed)), "error": "x", "uncertain": False}])
    m, f = aj.ensure_managed_campaign(led, sess(), business_id="b", promotion_id="p", connection_id="c")
    assert m.status == "ready" and f[0]["step"] == "ad_managed_reclaimed"


def test_auth_error_refreshes_once():
    class Expired(aj.DryRunDirectProvider):
        def find_managed_campaign(self, access_token, campaign_name):
            if access_token == "t":
                raise aj.DirectError("provider_53")
            return "ext-1"

    s = sess(Expired())
    m, _ = aj.ensure_managed_campaign(aj.Ledger(), s, business_id="b", promotion_id="p", connection_id="c")
    assert m.external_campaign_id == "ext-1" and s.refreshed["access_token"] == "dry-refreshed"


def test_submit_draft_with_image_then_resync_and_failures():
    p = aj.DryRunDirectProvider()
    q = aj.queue_job(aj.Ledger(), promotion_id="p", connection_id="c", external_campaign_id="e", region_ids=(213,),
                     title="T", text="X", source_url="https://x")
    led = aj.replay([q])
    assert aj.queue_job(led, promotion_id="p", connection_id="c", external_campaign_id="e", region_ids=(213,),
                        title="T", text="X", source_url="https://x") is None
    asset = am.replay(am.attach_image({}, q["job_id"], b"\xff\xd8\xffxx", uploader=lambda *a: "img")[1])[q["job_id"]]
    out = aj.submit(led, sess(p), q["job_id"], asset)
    assert out.media == (True, False, False) and out.job.status == "submitted"
    led2 = aj.replay([q, *out.facts])
    assert led2.jobs[q["job_id"]].ad_id == out.job.ad_id
    again = aj.submit(led2, sess(p), q["job_id"], asset)
    assert again.media == (True, False, False) and not any(c[0] == "publish_draft" for c in p.calls[-3:])
    assert not any("enable" in c[0] or "spend" in c[0] for c in p.calls)

    class Down(aj.DryRunDirectProvider):
        def publish_text_ad(self, *a):
            raise aj.DirectError("provider_http_503", retryable=True)

    fail = aj.submit(led, sess(Down()), q["job_id"], None)
    led3 = aj.replay([q, *fail.facts])
    assert fail.job is None and led3.jobs[q["job_id"]].status == "queued" and led3.jobs[q["job_id"]].attempts == 1
    out1 = aj.process_one(led3, lambda j: sess(), {})
    assert out1.job.status == "submitted"


def test_video_pending_then_ready_extension():
    p = aj.DryRunDirectProvider()
    q = aj.queue_job(aj.Ledger(), promotion_id="p", connection_id="c", external_campaign_id="e", region_ids=(1,),
                     title="T", text="X", source_url="https://x")
    afacts = am.attach_video({}, q["job_id"], b"v" * 9, content_type="video/mp4", name="a.mp4", duration_seconds=10,
                             uploader=lambda *a: "vid")[1]
    assets = am.replay(afacts)
    p.video["vid"] = "CONVERTING"
    out = aj.submit(aj.replay([q]), aj.Session(p, {"access_token": "t"}), q["job_id"], assets[q["job_id"]])
    assert out.media == (False, True, False)
    led = aj.replay([q, *out.facts])
    assert aj.process_pending_video(led, lambda j: aj.Session(p, {"access_token": "t"}), assets) == []
    p.video["vid"] = "READY"
    facts = aj.process_pending_video(led, lambda j: aj.Session(p, {"access_token": "t"}), assets)
    assert facts[0]["creative_id"] and am.replay(afacts + facts)[q["job_id"]].creative_id == facts[0]["creative_id"]
    p.video["vid"] = "ERROR"
    assets = am.replay(afacts)
    err = aj.process_pending_video(led, lambda j: aj.Session(p, {"access_token": "t"}), assets)
    assert err[0]["error"] == "ad_video_processing_failed" and am.replay(afacts + err)[q["job_id"]].error
