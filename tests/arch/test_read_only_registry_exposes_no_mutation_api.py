from runtime.read_only_registry import ReadOnlyRuntimeRegistry


def test_read_only_registry_exposes_no_mutation_api() -> None:
    forbidden = {
        "register",
        "seal",
        "begin_registration",
    }

    public_names = {name for name in dir(ReadOnlyRuntimeRegistry) if not name.startswith("_")}
    assert forbidden.isdisjoint(public_names)
