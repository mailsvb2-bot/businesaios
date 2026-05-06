from interfaces.common.registry_capability_contract import build_registry_entry


CONNECTORS = {
    "google_reviews": build_registry_entry(
        name="google_reviews",
        status="implemented",
        read=True,
        write=False,
        verify=False,
        supports_dry_run=False,
        supports_idempotency=False,
        production_ready=False,
        action_types=("request_review",),
    ),
    "trustpilot": build_registry_entry(name="trustpilot", status="not_implemented"),
    "yelp_reviews": build_registry_entry(name="yelp_reviews", status="not_implemented"),
}
