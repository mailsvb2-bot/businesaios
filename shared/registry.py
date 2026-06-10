from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Iterable, MutableMapping, TypeVar

T = TypeVar('T')


@dataclass
class Registry(Generic[T]):
    namespace: str
    _items: MutableMapping[str, T] = field(default_factory=dict)

    def register(self, key: str, value: T) -> None:
        normalized = self._normalize(key)
        if normalized in self._items:
            raise ValueError(f'duplicate registry key in {self.namespace}: {normalized}')
        self._items[normalized] = value

    def replace(self, key: str, value: T) -> None:
        self._items[self._normalize(key)] = value

    def get(self, key: str) -> T:
        normalized = self._normalize(key)
        if normalized not in self._items:
            raise KeyError(f'unknown registry key in {self.namespace}: {normalized}')
        return self._items[normalized]

    def maybe_get(self, key: str) -> T | None:
        return self._items.get(self._normalize(key))

    def items(self) -> Iterable[tuple[str, T]]:
        return tuple(self._items.items())

    def values(self) -> Iterable[T]:
        return tuple(self._items.values())

    def keys(self) -> Iterable[str]:
        return tuple(self._items.keys())

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self._normalize(key) in self._items

    def __len__(self) -> int:
        return len(self._items)

    def _normalize(self, key: str) -> str:
        normalized = key.strip()
        if not normalized:
            raise ValueError(f'empty registry key in {self.namespace}')
        return normalized


class ServiceRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('services')


class ComponentRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('components')


class ConnectorRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('connectors')


class ActionRunnerRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('action_runners')


class PolicyRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('policies')


class ModelRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('models')


class TemplateRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('templates')


class ExperimentRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('experiments')


class ActionRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('actions')


class OpportunityRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('opportunities')


class InputRegistry(Registry[object]):
    def __init__(self) -> None:
        super().__init__('decision_inputs')
