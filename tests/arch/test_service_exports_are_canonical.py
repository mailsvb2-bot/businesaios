from runtime.service_exports import RuntimeServiceExports


def test_service_exports_are_canonical() -> None:
    public_names = {name for name in RuntimeServiceExports.__dataclass_fields__.keys()}
    assert public_names == {"decision_execution", "observability"}
