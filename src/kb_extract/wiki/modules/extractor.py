"""Orchestrate module assignment over kb/ atoms (pure compute, no LLM)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ...layout import kb_dir as _kb_dir
from ..atoms.schema import Atom
from ..requirements.sections import iter_content_sections
from .classifier import classify
from .render import write_modules
from .rules import load_rules


@dataclass(slots=True)
class ModulesResult:
    modules_by_doc: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    pending_by_doc: dict[str, list[str]] = field(default_factory=dict)

    @property
    def docs(self) -> int:
        return len(self.modules_by_doc)

    @property
    def total_assigned(self) -> int:
        return sum(len(ids) for m in self.modules_by_doc.values() for ids in m.values())


def _load_atoms(graph_dir: Path) -> list[Atom]:
    f = graph_dir / "atoms.json"
    if not f.is_file():
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    out: list[Atom] = []
    for o in data:
        out.append(
            Atom(
                id=o["id"], entity=o["entity"], parameter=o["parameter"], value=o["value"],
                unit=o["unit"], type=o["type"], condition=o["condition"],
                source_doc=o["source_doc"], section=o["section"],
                evidence_ref=o["evidence_ref"], confidence=o.get("confidence", 0.0),
                flags=tuple(o.get("flags", [])),
            )
        )
    return out


def build_modules(
    project_root: Path, *, output_dir: Path | None = None, write: bool = True
) -> ModulesResult:
    kb_root = _kb_dir(project_root, output_dir)
    rules = load_rules()
    result = ModulesResult()
    if not kb_root.is_dir():
        return result
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        doc_id = doc_dir.name
        atoms = _load_atoms(doc_dir / "graph")
        if not atoms:
            continue
        sec_cat = {s.anchor: s.category for s in iter_content_sections(kb_root, doc_id)}
        buckets: dict[str, list[str]] = {m: [] for m in rules.modules}
        pending: list[str] = []
        for a in atoms:
            module, is_pending = classify(a, sec_cat.get(a.section, ""), rules)
            buckets[module].append(a.id)
            if is_pending:
                pending.append(a.id)
        for m in buckets:
            buckets[m].sort()
        pending.sort()
        result.modules_by_doc[doc_id] = buckets
        result.pending_by_doc[doc_id] = pending
        if write:
            write_modules(doc_dir, doc_id, atoms, buckets, pending, rules)
    return result
