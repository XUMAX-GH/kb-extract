"""Compose chat messages for atom extraction: base_system_rules + atoms_rules."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from ..providers.base import Message

_ASSETS = Path(__file__).with_name("assets")
_SEP = "\n\n---\n\n"


@cache
def _read_asset(rel: str) -> str:
    return (_ASSETS / rel).read_text(encoding="utf-8")


def build_system_prompt() -> str:
    return _SEP.join(
        [
            _read_asset("base_system_rules.md").rstrip(),
            _read_asset("atoms_rules.md").rstrip(),
        ]
    )


def build_user_prompt(*, anchor: str, section_title: str, section_body: str) -> str:
    ev = json.dumps(
        [{"id": anchor, "type": "text", "section": section_title, "content": section_body}],
        ensure_ascii=False,
        indent=2,
    )
    return _read_asset("user_template.md").replace("{evidence_content}", ev)


def compose_messages(*, anchor: str, section_title: str, section_body: str) -> list[Message]:
    return [
        {"role": "system", "content": build_system_prompt()},
        {
            "role": "user",
            "content": build_user_prompt(
                anchor=anchor, section_title=section_title, section_body=section_body
            ),
        },
    ]
