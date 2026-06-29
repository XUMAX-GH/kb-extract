"""Render edges to canonical edges.json + an Obsidian-friendly graph.md view."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ...serialization import serialize_markdown
from ..atoms.schema import Atom
from .schema import RELATIONS, Edge


def render_json(edges: list[Edge]) -> str:
    return json.dumps([e.to_dict() for e in edges], ensure_ascii=False, indent=2) + "\n"


def _label(a: Atom | None, edge_id: str) -> str:
    if a is None:
        return edge_id
    return f"[[{a.parameter}]] ({a.entity})"


def render_markdown(doc_id: str, edges: list[Edge], by_id: dict[str, Atom]) -> str:
    if not edges:
        return serialize_markdown(f"# Graph: {doc_id}\n\n_No edges._")
    grouped: dict[str, list[Edge]] = defaultdict(list)
    for e in edges:
        grouped[e.relation].append(e)
    lines = [f"# Graph: {doc_id}", "", f"_{len(edges)} edges._", ""]
    for rel in RELATIONS:
        items = grouped.get(rel, [])
        if not items:
            continue
        lines += [f"## {rel}", ""]
        for e in items:
            pend = " [待验证]" if "待验证" in e.flags else ""
            lines.append(
                f"- {_label(by_id.get(e.source_id), e.source_id)} -> "
                f"{_label(by_id.get(e.target_id), e.target_id)} "
                f"(conf {e.confidence:.2f}){pend}"
            )
        lines.append("")
    return serialize_markdown("\n".join(lines))


def write_graph(doc_dir: Path, doc_id: str, edges: list[Edge], atoms: list[Atom]) -> None:
    graph = doc_dir / "graph"
    graph.mkdir(parents=True, exist_ok=True)
    by_id = {a.id: a for a in atoms}
    (graph / "edges.json").write_bytes(render_json(edges).encode("utf-8"))
    (graph / "graph.md").write_bytes(render_markdown(doc_id, edges, by_id).encode("utf-8"))
