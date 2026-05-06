from __future__ import annotations

from typing import Any

from application.public_site.landing_content import PUBLIC_SITE_SECTION_ORDER, build_landing_payload, build_public_capabilities_payload
from interfaces.web.public_site.landing_manifest import PUBLIC_SITE_MANIFEST

CANON_PUBLIC_SITE_SERVICE = True


class PublicSiteService:
    """Application owner for public landing content and truthful capability publication."""

    def landing(self, *, include_roadmap: bool = True) -> dict[str, Any]:
        payload = build_landing_payload(include_roadmap=include_roadmap)
        return self._with_publication_status(payload)

    def capabilities(self, *, include_roadmap: bool = True) -> dict[str, Any]:
        return build_public_capabilities_payload(include_roadmap=include_roadmap)

    def admin_status(self) -> dict[str, Any]:
        landing = self.landing(include_roadmap=True)
        capability_cards = landing['sections']['capabilities']['cards']
        violations = self._publication_violations(capability_cards)
        return {
            'surface': 'public_site',
            'manifest': dict(PUBLIC_SITE_MANIFEST),
            'sections_order': list(PUBLIC_SITE_SECTION_ORDER),
            'sections_count': len(PUBLIC_SITE_SECTION_ORDER),
            'safe_to_publish': not violations,
            'violations': violations,
            'capabilities_summary': landing['capabilities']['summary'],
            'guards': landing['sections']['capabilities']['policy'],
            'endpoints': {
                'landing': '/public-site/landing',
                'capabilities': '/public-site/capabilities',
                'admin_status': '/control-plane/public-site/status',
            },
        }

    def _with_publication_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        cards = payload['sections']['capabilities']['cards']
        violations = self._publication_violations(cards)
        payload = dict(payload)
        payload['publication'] = {
            'safe_to_publish': not violations,
            'violations': violations,
            'policy': payload['sections']['capabilities']['policy'],
        }
        return payload

    @staticmethod
    def _publication_violations(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []
        for item in cards:
            if item.get('roadmap_only') and item.get('connectable'):
                violations.append(
                    {
                        'id': item.get('id'),
                        'reason': 'roadmap-only capability is marked connectable',
                    }
                )
        return violations


__all__ = ['CANON_PUBLIC_SITE_SERVICE', 'PublicSiteService']
