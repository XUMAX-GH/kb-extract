"""Compose chat messages for edge extraction: base_system_rules + graph_rules."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from ..providers.base import Message

_ASSETS = Path(__file__).with_name("assets")
_BASE = Path(__file__).resolve().parent.parent / "atoms" / "assets"
_SEP = "\n\n---\n\n"


@cache
def _read_asset(rel: str) -> str:
    return (_ASSETS / rel).read_text(encoding="utf-8")


@cache
def _read_base(rel: str) -> str:
    return (_BASE / rel).read_text(encoding="utf-8")


def build_system_prompt() -> str:
    return _SEP.join(
        [
            _read_base("base_system_rules.md").rstrip(),
            _read_asset("graph_rules.md").rstrip(),
        ]
    )


def build_user_prompt(*, atoms: list[dict]) -> str:
    body = json.dumps(atoms, ensure_ascii=False, indent=2)
    return _read_asset("user_template.md").replace("{atoms_content}", body)


def compose_messages(*, atoms: list[dict]) -> list[Message]:
    return [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": build_user_prompt(atoms=atoms)},
    ]
