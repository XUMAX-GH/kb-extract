"""Orchestrate edge extraction over kb/ atoms+modules (wiki layer, LLM-backed).

Atoms are immutable. Edges are proposed per module batch; hallucinated ids and
relations are dropped by code. Edges sorted/deduped -> byte-reproducible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ...layout import kb_dir as _kb_dir
from ..atoms.schema import Atom
from ..providers.base import LlmClient
from .prompts import compose_messages
from .schema import Edge, coerce_edge, parse_edges


@dataclass(slots=True)
class GraphResult:
    edges_by_doc: dict[str, list[Edge]] = field(default_factory=dict)
    ok_batches: int = 0
    failed_batches: int = 0

    @property
    def docs(self) -> int:
        return len(self.edges_by_doc)

    @property
    def total_edges(self) -> int:
        return sum(len(v) for v in self.edges_by_doc.values())

    @property
    def total_pending(self) -> int:
        return sum(1 for v in self.edges_by_doc.values() for e in v if "待验证" in e.flags)


def _load_atoms(graph_dir: Path) -> list[Atom]:
    f = graph_dir / "atoms.json"
    if not f.is_file():
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    return [
        Atom(
            id=o["id"], entity=o["entity"], parameter=o["parameter"], value=o["value"],
            unit=o["unit"], type=o["type"], condition=o["condition"],
            source_doc=o["source_doc"], section=o["section"],
            evidence_ref=o["evidence_ref"], confidence=o.get("confidence", 0.0),
            flags=tuple(o.get("flags", [])),
        )
        for o in data
    ]


def _load_modules(graph_dir: Path) -> dict[str, list[str]]:
    f = graph_dir / "modules.json"
    if not f.is_file():
        return {}
    return json.loads(f.read_text(encoding="utf-8"))


def _atom_brief(a: Atom) -> dict:
    return {"id": a.id, "entity": a.entity, "parameter": a.parameter,
            "value": a.value, "type": a.type}


def extract_graph(
    project_root: Path, llm: LlmClient, *,
    output_dir: Path | None = None, dry_run: bool = False,
) -> GraphResult:
    kb_root = _kb_dir(project_root, output_dir)
    result = GraphResult()
    if not kb_root.is_dir():
        return result
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        doc_id = doc_dir.name
        atoms = _load_atoms(doc_dir / "graph")
        if not atoms:
            continue
        valid_ids = {a.id for a in atoms}
        modules = _load_modules(doc_dir / "graph")
        batches = [ids for m, ids in modules.items() if m != "_pending" and ids] or [
            sorted(valid_ids)
        ]
        seen: set[tuple[str, str, str]] = set()
        edges: list[Edge] = []
        for ids in batches:
            briefs = [_atom_brief(a) for a in atoms if a.id in set(ids)]
            if not briefs:
                continue
            try:
                raw = llm.chat(compose_messages(atoms=briefs))
                if dry_run:
                    result.ok_batches += 1
                    continue
                for obj in parse_edges(raw):
                    e = coerce_edge(obj, doc_id=doc_id, valid_ids=valid_ids)
                    if e is None:
                        continue
                    key = e.sort_key()
                    if key in seen:
                        continue
                    seen.add(key)
                    edges.append(e)
                result.ok_batches += 1
            except Exception:
                result.failed_batches += 1
                continue
        if edges:
            edges.sort(key=lambda e: e.sort_key())
            result.edges_by_doc[doc_id] = edges
    return result
