"""Compose chat messages for requirement extraction from bundled assets."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from ..providers.base import Message
from .router import FALLBACK_DOMAIN

_ASSETS = Path(__file__).with_name("assets")
_SEP = "\n\n---\n\n"


@cache
def _read_asset(rel: str) -> str:
    return (_ASSETS / rel).read_text(encoding="utf-8")


def _domain_skill(domain: str) -> str:
    path = _ASSETS / "domains" / f"{domain}.md"
    if not path.is_file():
        path = _ASSETS / "domains" / f"{FALLBACK_DOMAIN}.md"
    return path.read_text(encoding="utf-8")


def build_system_prompt(domain: str) -> str:
    return _SEP.join(
        [
            _read_asset("base_extraction.md").rstrip(),
            _domain_skill(domain).rstrip(),
            _read_asset("p1_rules.md").rstrip(),
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
    *, domain: str, anchor: str, section_title: str, section_body: str
) -> list[Message]:
    return [
        {"role": "system", "content": build_system_prompt(domain)},
        {
            "role": "user",
            "content": build_user_prompt(
                anchor=anchor,
                section_title=section_title,
                section_body=section_body,
            ),
        },
    ]
