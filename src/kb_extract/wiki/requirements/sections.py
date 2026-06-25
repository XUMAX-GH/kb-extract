"""Walk every content-bearing section of a generated ``main.md``.

Unlike the topic pipeline (which collects only index *leaves*), requirement
extraction needs *every* section that carries real content -- including
mid-level headings whose body holds a requirement summary table. Each
section is tagged with the document's own top-level (level-1) chapter
heading, which is used as the requirement Category. This keeps grouping
fully deterministic and traceable to the document's own structure -- no
keyword routing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Splits main.md into per-section segments. The anchor id is captured so we
# can attach it as the EvidenceRef.
_SEC_RE = re.compile(r'<a id="(sec-\d+)"></a>')
# First markdown ATX heading line inside a segment: "## Title".
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ContentSection:
    anchor: str
    title: str
    level: int
    category: str
    body: str


def chunk_body(body: str, *, max_chars: int) -> list[str]:
    """Split ``body`` into <= ``max_chars`` chunks without dropping content.

    Splits on paragraph boundaries (blank lines) first; a single paragraph
    longer than ``max_chars`` is hard-split on line boundaries, and a single
    line longer than ``max_chars`` is hard-split by character. The original
    text is never truncated -- every chunk together preserves all content.
    """
    if len(body) <= max_chars:
        return [body]

    def hard_split(text: str) -> list[str]:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    units: list[str] = []
    for para in body.split("\n\n"):
        if len(para) <= max_chars:
            units.append(para)
            continue
        for line in para.split("\n"):
            if len(line) <= max_chars:
                units.append(line)
            else:
                units.extend(hard_split(line))

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else f"{current}\n\n{unit}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = unit
    if current:
        chunks.append(current)
    return chunks


def iter_content_sections(kb_root: Path, doc_id: str) -> list[ContentSection]:
    """Return every content-bearing section of ``doc_id``'s ``main.md``.

    Heading-only container sections (no body beyond the heading) are skipped.
    Sections are returned in document order. ``category`` is the most recent
    level-1 heading at or above the section (a level-1 section that carries
    its own body uses its own title).
    """
    main_md = Path(kb_root) / doc_id / "main.md"
    if not main_md.is_file():
        return []

    text = main_md.read_text(encoding="utf-8")
    matches = list(_SEC_RE.finditer(text))
    out: list[ContentSection] = []
    current_top = ""

    for i, m in enumerate(matches):
        anchor = m.group(1)
        seg_start = m.end()
        seg_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[seg_start:seg_end]

        hm = _HEADING_RE.search(segment)
        if hm is None:
            continue
        level = len(hm.group(1))
        title = hm.group(2).strip()
        body = segment[hm.end() :].strip()

        if level == 1:
            current_top = title
        category = current_top or title

        if not body:
            continue

        out.append(
            ContentSection(
                anchor=anchor,
                title=title,
                level=level,
                category=category,
                body=body,
            )
        )
    return out
