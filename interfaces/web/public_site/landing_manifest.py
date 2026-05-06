from __future__ import annotations

PUBLIC_SITE_MANIFEST = {
    'surface': 'interfaces.web.public_site',
    'owner': 'application.public_site',
    'purpose': 'public landing and truthful capability publication',
    'capability_source_of_truth': 'application.business_autonomy.integration_capability_catalog',
    'admin_surface_required': True,
    'must_not_hardcode_capability_truth': True,
    'must_not_publish_roadmap_as_connectable': True,
}

__all__ = ['PUBLIC_SITE_MANIFEST']
