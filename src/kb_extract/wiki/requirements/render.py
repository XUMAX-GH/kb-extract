"""Render extracted requirements to canonical JSON + grouped Markdown."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ...serialization import serialize_markdown
from .models import TestItem


def render_json(items: list[TestItem]) -> str:
    payload = [it.to_dict() for it in items]
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_markdown(doc_id: str, items: list[TestItem]) -> str:
    lines: list[str] = [f"# Requirements: {doc_id}", ""]
    if not items:
        lines.append("_No requirements extracted._")
        return serialize_markdown("\n".join(lines))

    by_cat: dict[str, list[TestItem]] = defaultdict(list)
    for it in items:
        by_cat[it.category].append(it)

    for cat in sorted(by_cat):
        lines.append(f"## {cat}")
        lines.append("")
        for it in by_cat[cat]:
            link = f"[{it.evidence_ref}](main.md#{it.evidence_ref})"
            lines.append(f"- **{it.function or 'Requirement'}** ({link})")
            lines.append(f"  - What: {it.what}")
            lines.append(f"  - How: {it.how}")
            lines.append(f"  - Sample Size: {it.sample_size}")
            lines.append(f"  - Source: {it.source_document} / {it.source_section}")
            if it.evidence_quote:
                lines.append(f"  - Evidence: > {it.evidence_quote}")
            lines.append("")
    return serialize_markdown("\n".join(lines))


def write_requirements(doc_dir: Path, doc_id: str, items: list[TestItem]) -> None:
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "requirements.json").write_bytes(render_json(items).encode("utf-8"))
    (doc_dir / "requirements.md").write_bytes(
        render_markdown(doc_id, items).encode("utf-8")
    )
