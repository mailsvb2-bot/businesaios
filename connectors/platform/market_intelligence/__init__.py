"""Canonical platform registry helpers for market intelligence connectors."""

from connectors.platform.market_intelligence.registry_bundle import build_market_intelligence_registry_entries


CANON_MARKET_INTELLIGENCE_PLATFORM_PACKAGE = True

PACKAGE_EXPORTS = ('build_market_intelligence_registry_entries',)


def package_contract() -> dict[str, object]:
    return {
        'canonical': True,
        'exports': list(PACKAGE_EXPORTS),
        'purpose': 'market intelligence connector registry bundle',
    }


__all__ = ['CANON_MARKET_INTELLIGENCE_PLATFORM_PACKAGE', 'PACKAGE_EXPORTS', 'build_market_intelligence_registry_entries', 'package_contract']
