from dataclasses import dataclass


@dataclass
class RuntimeState:
    booted: bool = False
    ready: bool = False
    shutting_down: bool = False
