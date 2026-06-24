"""Orchestrate requirement extraction over a kb/ tree (wiki layer)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ...layout import kb_dir as _kb_dir
from ..providers.base import LlmClient
from ..sections import read_section_body
from ..topics import EvidenceRef, _walk_index
from .models import TestItem, coerce_item, parse_items
from .prompts import compose_messages
from .router import route_heading


@dataclass(slots=True)
class RequirementsResult:
    items_by_doc: dict[str, list[TestItem]] = field(default_factory=dict)
    ok_sections: int = 0
    failed_sections: int = 0

    @property
    def docs(self) -> int:
        return len(self.items_by_doc)

    @property
    def total_items(self) -> int:
        return sum(len(v) for v in self.items_by_doc.values())


def _doc_evidence(kb_root: Path, doc_id: str) -> list[EvidenceRef]:
    index_file = kb_root / doc_id / "index.json"
    if not index_file.is_file():
        return []
    try:
        root = json.loads(index_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    collected: list[tuple[EvidenceRef, frozenset[str]]] = []
    _walk_index(root, doc_id, collected)
    return [ev for ev, _tokens in collected]


def extract_requirements(
    project_root: Path,
    llm: LlmClient,
    *,
    output_dir: Path | None = None,
    max_chars: int = 1500,
    dry_run: bool = False,
) -> RequirementsResult:
    """Route + prompt + extract requirements for every section under kb/.

    Per-section failures are isolated: a parse/LLM error increments
    ``failed_sections`` and processing continues. With ``dry_run=True`` the
    LLM is still called (to surface provider/cache issues) but the response
    is not parsed into items.
    """
    kb_root = _kb_dir(project_root, output_dir)
    result = RequirementsResult()
    if not kb_root.is_dir():
        return result

    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        doc_id = doc_dir.name
        items: list[TestItem] = []
        for ev in _doc_evidence(kb_root, doc_id):
            title = ev.section_title
            anchor = ev.anchor
            body = read_section_body(kb_root, doc_id, anchor, max_chars=max_chars)
            if not body:
                continue
            domain = route_heading(title).domain
            messages = compose_messages(
                domain=domain,
                anchor=anchor,
                section_title=title,
                section_body=body,
            )
            try:
                raw = llm.chat(messages)
                if dry_run:
                    result.ok_sections += 1
                    continue
                for obj in parse_items(raw):
                    items.append(coerce_item(obj, anchor=anchor, section_title=title))
                result.ok_sections += 1
            except Exception:  # per-section fault tolerance
                result.failed_sections += 1
                continue
        if items:
            items.sort(key=lambda it: it.sort_key())
            result.items_by_doc[doc_id] = items
    return result
