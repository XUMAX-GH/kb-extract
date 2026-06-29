"""Generate Wiki narrative pages (What/Why/How) from atoms, bilingual.

LLM writes prose per entity; code aggregates atoms, stamps invariants, and links
evidence back to RawMD#section. Multi-doc entities get a [冲突]-aware compare
page. Pages sorted -> reproducible. LLM failure falls back to a deterministic
atoms listing so a page is always produced.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..layout import kb_dir as _kb_dir
from ..serialization import serialize_markdown
from ..wiki.atoms.schema import Atom
from ..wiki.providers.base import LlmClient
from .prompts import compose_whatwhyhow

_MAX_ATOMS_PER_ENTITY = 40


@dataclass(slots=True)
class WikiResult:
    pages: int = 0
    ok: int = 0
    failed: int = 0
    entities: list[str] = field(default_factory=list)


def _load_atoms(graph_dir: Path) -> list[Atom]:
    f = graph_dir / "atoms.json"
    if not f.is_file():
        return []
    return [
        Atom(id=o["id"], entity=o["entity"], parameter=o["parameter"], value=o["value"],
             unit=o["unit"], type=o["type"], condition=o["condition"],
             source_doc=o["source_doc"], section=o["section"], evidence_ref=o["evidence_ref"],
             confidence=o.get("confidence", 0.0), flags=tuple(o.get("flags", [])))
        for o in json.loads(f.read_text(encoding="utf-8"))
    ]


def _brief(a: Atom) -> dict:
    return {"parameter": a.parameter, "value": a.value, "unit": a.unit,
            "condition": a.condition, "doc": a.source_doc, "section": a.section}


def _evidence_lines(atoms: list[Atom]) -> list[str]:
    lines = ["## Evidence / 证据", ""]
    for a in sorted(atoms, key=lambda x: (x.source_doc, x.section, x.parameter)):
        val = a.value if a.value is not None else "[待验证]"
        unit = f" {a.unit}" if a.unit else ""
        lines.append(
            f"- [[{a.parameter}]]: {val}{unit} "
            f"([{a.source_doc}#{a.section}](../../RawMD/{a.source_doc}.md#{a.section}))"
        )
    lines.append("")
    return lines


def _entity_page(entity: str, atoms: list[Atom], body: str) -> str:
    head = [f"# [[{entity}]]", "", "[新增] [来源:graph/atoms.json] [置信度:中]", ""]
    parts = [*head, body.strip(), "", *_evidence_lines(atoms)]
    return serialize_markdown("\n".join(parts))


def _fallback_body(entity: str) -> str:
    return f"## What\n[[{entity}]] [待验证]\n\n## Why\n[待验证]\n\n## How\n[待验证]"


def _compare_page(entity: str, per_doc: dict[str, list[Atom]]) -> str:
    lines = [f"# Compare: [[{entity}]]", "", "[冲突] 多文档出现 需人工判断。", ""]
    for doc in sorted(per_doc):
        lines.append(f"## [[{doc}]]")
        for a in sorted(per_doc[doc], key=lambda x: x.parameter):
            val = a.value if a.value is not None else "[待验证]"
            lines.append(f"- [[{a.parameter}]]: {val} {a.unit}".rstrip())
        lines.append("")
    return serialize_markdown("\n".join(lines))


def generate_wiki(project_root: Path, llm: LlmClient, *,
                  output_dir: Path | None = None, dry_run: bool = False,
                  skip_existing: bool = False) -> WikiResult:
    kb_root = _kb_dir(project_root, output_dir)
    result = WikiResult()
    if not kb_root.is_dir():
        return result
    base = output_dir if output_dir is not None else project_root
    wiki = Path(base).resolve() / "vault" / "Wiki"
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    (wiki / "compare").mkdir(parents=True, exist_ok=True)
    by_entity_doc: dict[str, dict[str, list[Atom]]] = defaultdict(lambda: defaultdict(list))
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        for a in _load_atoms(doc_dir / "graph"):
            by_entity_doc[a.entity][a.source_doc].append(a)
    for entity in sorted(by_entity_doc):
        per_doc = by_entity_doc[entity]
        flat = [a for v in per_doc.values() for a in v]
        fname = entity.replace("/", "-").replace(" ", "_")
        if skip_existing and (wiki / "entities" / f"{fname}.md").exists():
            continue
        body = _fallback_body(entity)
        try:
            raw = llm.chat(compose_whatwhyhow(
                entity=entity, atoms=[_brief(a) for a in flat[:_MAX_ATOMS_PER_ENTITY]]))
            if not dry_run:
                body = raw.strip() or body
            result.ok += 1
        except Exception:
            result.failed += 1
        if dry_run:
            continue
        (wiki / "entities" / f"{fname}.md").write_bytes(
            _entity_page(entity, flat, body).encode("utf-8"))
        result.entities.append(entity)
        result.pages += 1
        if len(per_doc) >= 2:
            (wiki / "compare" / f"{fname}.md").write_bytes(
                _compare_page(entity, per_doc).encode("utf-8"))
            result.pages += 1
    return result
