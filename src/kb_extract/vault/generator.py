"""Generate Wiki narrative pages (overview + entity + compare) from atoms.

LLM writes prose; code aggregates atoms and stamps invariants. Multi-doc entities
get a [冲突]-aware compare page. Pages sorted -> byte-reproducible.
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
from .prompts import compose_overview


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
    return {"entity": a.entity, "parameter": a.parameter, "value": a.value, "unit": a.unit}


def _entity_page(entity: str, atoms: list[Atom]) -> str:
    lines = [f"# [[{entity}]]", "", "[新增] [来源:graph/atoms.json] [置信度:中]", ""]
    for a in sorted(atoms, key=lambda x: (x.source_doc, x.parameter)):
        val = a.value if a.value is not None else "[待验证]"
        unit = f" {a.unit}" if a.unit else ""
        lines.append(f"- [[{a.parameter}]]: {val}{unit} ([{a.source_doc}](../RawMD/{a.source_doc}.md))")
    lines.append("")
    return serialize_markdown("\n".join(lines))


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
                  output_dir: Path | None = None, dry_run: bool = False) -> WikiResult:
    kb_root = _kb_dir(project_root, output_dir)
    result = WikiResult()
    if not kb_root.is_dir():
        return result
    base = (output_dir if output_dir is not None else project_root)
    wiki = Path(base).resolve() / "vault" / "Wiki"
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    (wiki / "compare").mkdir(parents=True, exist_ok=True)
    by_entity_doc: dict[str, dict[str, list[Atom]]] = defaultdict(lambda: defaultdict(list))
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        atoms = _load_atoms(doc_dir / "graph")
        for a in atoms:
            by_entity_doc[a.entity][a.source_doc].append(a)
        if atoms:
            try:
                raw = llm.chat(compose_overview(atoms=[_brief(a) for a in atoms]))
                result.ok += 1
                if not dry_run:
                    (wiki / f"{doc_dir.name}.md").write_bytes(
                        serialize_markdown(f"# {doc_dir.name}\n\n{raw}").encode("utf-8"))
                    result.pages += 1
            except Exception:
                result.failed += 1
    if dry_run:
        return result
    for entity in sorted(by_entity_doc):
        per_doc = by_entity_doc[entity]
        flat = [a for v in per_doc.values() for a in v]
        fname = entity.replace("/", "-").replace(" ", "_")
        (wiki / "entities" / f"{fname}.md").write_bytes(_entity_page(entity, flat).encode("utf-8"))
        result.entities.append(entity)
        result.pages += 1
        if len(per_doc) >= 2:
            (wiki / "compare" / f"{fname}.md").write_bytes(_compare_page(entity, per_doc).encode("utf-8"))
            result.pages += 1
    return result
