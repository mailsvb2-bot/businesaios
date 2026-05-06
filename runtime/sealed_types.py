from __future__ import annotations

class SealedType:
    """
    Base class for runtime-critical sealed types.
    Direct subclass is allowed once.
    Further subclassing is forbidden.
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        for base in cls.__bases__:
            if base is SealedType:
                continue

            if issubclass(base, SealedType):
                raise TypeError(
                    f"Subclassing sealed runtime type '{base.__name__}' is forbidden."
                )
