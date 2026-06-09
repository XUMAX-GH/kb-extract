"""Extractor protocol and adapter registry.

Adapters register themselves via `@register` at import time. The orchestrator
holds a `Registry` instance and calls `pick(src)` to choose one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..contracts import ExtractionResult


@runtime_checkable
class Extractor(Protocol):
    name: str
    version: str
    extensions: tuple[str, ...]

    def extract(self, src: Path, out_dir_tmp: Path) -> ExtractionResult:
        ...


class Registry:
    def __init__(self) -> None:
        self._by_ext: dict[str, Extractor] = {}
        self._adapters: list[Extractor] = []

    def register(self, adapter: Extractor) -> None:
        for ext in adapter.extensions:
            key = ext.lower()
            if key in self._by_ext:
                raise ValueError(
                    f"adapter for extension {key!r} already registered: "
                    f"{self._by_ext[key].name}"
                )
            self._by_ext[key] = adapter
        self._adapters.append(adapter)

    def pick(self, src: Path) -> Extractor | None:
        return self._by_ext.get(src.suffix.lower())

    def all(self) -> list[Extractor]:
        return list(self._adapters)


_DEFAULT: Registry = Registry()


def get_default_registry() -> Registry:
    return _DEFAULT


def register(adapter_cls):
    """Decorator that instantiates and registers an adapter on the default registry."""
    instance = adapter_cls()
    _DEFAULT.register(instance)
    return adapter_cls
