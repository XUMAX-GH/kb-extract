"""Load the deterministic module rules table."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

_ASSETS = Path(__file__).with_name("assets")


@dataclass(frozen=True, slots=True)
class ModuleRules:
    modules: tuple[str, ...]
    category_to_module: dict[str, str]
    keyword_to_module: dict[str, tuple[str, ...]]
    fallback: str


@cache
def load_rules() -> ModuleRules:
    raw = json.loads((_ASSETS / "module_rules.json").read_text(encoding="utf-8"))
    return ModuleRules(
        modules=tuple(raw["modules"]),
        category_to_module={k.lower(): v for k, v in raw["category_to_module"].items()},
        keyword_to_module={k: tuple(v) for k, v in raw["keyword_to_module"].items()},
        fallback=raw["fallback"],
    )
