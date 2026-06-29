"""Compose messages for Wiki narrative pages: base rules + vault wiki rules."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from ..wiki.providers.base import Message

_ASSETS = Path(__file__).with_name("assets")
_BASE = Path(__file__).resolve().parent.parent / "wiki" / "atoms" / "assets"


@cache
def _read(rel: str) -> str:
    return (_ASSETS / rel).read_text(encoding="utf-8")


@cache
def _base(rel: str) -> str:
    return (_BASE / rel).read_text(encoding="utf-8")


def build_system_prompt() -> str:
    return _base("base_system_rules.md").rstrip()


def compose_overview(*, atoms: list[dict]) -> list[Message]:
    body = json.dumps(atoms, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": _read("wiki_user.md").replace("{atoms_content}", body)},
    ]
