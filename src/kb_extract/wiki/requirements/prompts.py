"""Compose chat messages for requirement extraction from bundled assets.

System prompt = ``base_system_rules.md`` + ``p2_rules.md`` (CTx P2 precision
variant). There is no domain-skill layer: the document's own chapter heading
is passed through as the requirement Category (see ``sections.py``).
"""

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
            _read_asset("p2_rules.md").rstrip(),
        ]
    )


def _evidence_block(*, anchor: str, section_title: str, section_body: str) -> str:
    payload = [
        {
            "id": anchor,
            "type": "text",
            "section": section_title,
            "content": section_body,
        }
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_user_prompt(*, anchor: str, section_title: str, section_body: str) -> str:
    template = _read_asset("user_template.md")
    evidence = _evidence_block(
        anchor=anchor, section_title=section_title, section_body=section_body
    )
    return template.replace("{evidence_content}", evidence)


def compose_messages(
    *, anchor: str, section_title: str, section_body: str
) -> list[Message]:
    return [
        {"role": "system", "content": build_system_prompt()},
        {
            "role": "user",
            "content": build_user_prompt(
                anchor=anchor,
                section_title=section_title,
                section_body=section_body,
            ),
        },
    ]
