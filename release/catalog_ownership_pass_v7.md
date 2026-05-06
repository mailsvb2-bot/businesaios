# Catalog ownership pass v7

Collapsed the safest thin catalog surfaces into package-owner namespaces.

Collapsed:
- products/catalog.py
- demand_feedback/catalog.py
- marketplace/search/catalog.py
- lead_outcomes/catalog.py
- leads/catalog.py

Method:
- moved canonical exports into package ``__init__.py``
- preserved historical ``package.catalog`` imports through a static package-submodule alias
- updated one package-structure test and one runtime import

Deferred:
- execution/effectors/catalog.py remains a real owner surface
- core/actions/catalog.py remains a real owner surface
- boot/*/catalog.py remain real registries/factories and should not be collapsed blindly
