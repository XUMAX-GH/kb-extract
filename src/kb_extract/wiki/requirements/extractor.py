"""Orchestrate requirement extraction over a kb/ tree (wiki layer).

Walks every content-bearing section of each document's ``main.md`` (not just
index leaves), chunks long bodies without truncation, and tags each item with
the document's own top-level chapter heading as its Category. No keyword
routing -- the prompt is a single global P2 system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...layout import kb_dir as _kb_dir
from ..providers.base import LlmClient
from .models import TestItem, coerce_item, parse_items
from .prompts import compose_messages
from .sections import chunk_body, iter_content_sections

# Per-chunk body budget fed to the LLM. Long sections are split into multiple
# chunks (no truncation) so dense requirement summary tables are walked fully.
DEFAULT_MAX_CHARS = 6000


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


def extract_requirements(
    project_root: Path,
    llm: LlmClient,
    *,
    output_dir: Path | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    dry_run: bool = False,
) -> RequirementsResult:
    """Route + prompt + extract requirements for every section under kb/.

    Per-chunk failures are isolated: a parse/LLM error increments
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
        for sec in iter_content_sections(kb_root, doc_id):
            for chunk in chunk_body(sec.body, max_chars=max_chars):
                messages = compose_messages(
                    anchor=sec.anchor,
                    section_title=sec.title,
                    section_body=chunk,
                )
                try:
                    raw = llm.chat(messages)
                    if dry_run:
                        result.ok_sections += 1
                        continue
                    for obj in parse_items(raw):
                        items.append(
                            coerce_item(
                                obj,
                                anchor=sec.anchor,
                                section_title=sec.title,
                                category=sec.category,
                                section_body=chunk,
                            )
                        )
                    result.ok_sections += 1
                except Exception:  # per-chunk fault tolerance
                    result.failed_sections += 1
                    continue
        if items:
            items.sort(key=lambda it: it.sort_key())
            result.items_by_doc[doc_id] = items
    return result
