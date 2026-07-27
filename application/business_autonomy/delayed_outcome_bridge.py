from __future__ import annotations

from runtime.business_autonomy import delayed_outcome_bridge as _runtime_bridge

# Compatibility facade: the effectful delayed-outcome bridge belongs to runtime,
# while existing application imports keep the same public and test-facing API.
globals().update(
    {
        name: value
        for name, value in vars(_runtime_bridge).items()
        if not name.startswith("__")
    }
)

__all__ = _runtime_bridge.__all__

# Preserve stable import metadata for persisted references and introspection.
for _exported_name in __all__:
    _exported_value = globals().get(_exported_name)
    if getattr(_exported_value, "__module__", None) == _runtime_bridge.__name__:
        _exported_value.__module__ = __name__

del _exported_name
del _exported_value
