# Multimodal collapse pass v9

This pass bundled several ownership integrations in one shot:

1. Collapsed four thin `catalog.py` package-owner surfaces into their package roots:
   - `growth/platforms/catalog.py`
   - `market_balance/catalog.py`
   - `mvp/catalog.py`
   - `routing_execution/channels/catalog.py`
2. Preserved historical `package.catalog` imports via `install_package_submodule_alias(...)`.
3. Replaced three bespoke dynamic compat installers with the shared alias module helper:
   - `growth/seo/__init__.py`
   - `matching/scorers/__init__.py`
   - `routing/policies/__init__.py`
4. Removed the word `Synthetic` from the shared alias-module helper doc surface to better reflect explicit transition ownership rather than synthetic runtime matter.

The goal of this pass was to reduce surface proliferation and custom compat machinery without introducing any second decision path.
