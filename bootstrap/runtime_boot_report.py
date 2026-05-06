from __future__ import annotations

"""Final owner for runtime boot report.

Physical ownership moved from `boot/*` to `bootstrap/*`.
Legacy boot surfaces remain thin compatibility shells."""

CANON_RUNTIME_BOOT_REPORT_FINAL_OWNER = True
CANON_RUNTIME_BOOT_REPORT_NO_RUNTIME_ASSEMBLY = True


from dataclasses import dataclass, field

CANON_RUNTIME_BOOT_REPORT_INTERNAL_SUPPORT = True
CANON_RUNTIME_BOOT_REPORT_NO_PUBLIC_ENTRYPOINT = True
CANON_RUNTIME_BOOT_REPORT_DATA_ONLY = True


@dataclass(frozen=True)
class RuntimeBootRecord:
    name: str
    service_type: str
    implementation_type: str
    dependencies: tuple[str, ...] = field(default_factory=tuple)


class RuntimeBootReport:
    def __init__(self) -> None:
        self._records: list[RuntimeBootRecord] = []

    @property
    def records(self) -> tuple[RuntimeBootRecord, ...]:
        return tuple(self._records)

    def add(
        self,
        *,
        name: str,
        service_type: str,
        implementation_type: str,
        dependencies: tuple[str, ...] = (),
    ) -> None:
        self._records.append(
            RuntimeBootRecord(
                name=name,
                service_type=service_type,
                implementation_type=implementation_type,
                dependencies=tuple(dependencies),
            )
        )

    def service_names(self) -> tuple[str, ...]:
        return tuple(record.name for record in self._records)
