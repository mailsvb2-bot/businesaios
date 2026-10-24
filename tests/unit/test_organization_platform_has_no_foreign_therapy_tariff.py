"""Prevent unrelated therapy-course tariffs from leaking into the organization product."""

from core.plans.catalog import active_plans


def test_organization_platform_default_catalog_excludes_therapy_courses():
    plans = active_plans()
    assert not any(
        plan.get("scope") == "morning"
        or plan.get("plan_code") == "morning_5"
        or "Утро — 5 дней" in str(plan.get("title", ""))
        for plan in plans
    )
