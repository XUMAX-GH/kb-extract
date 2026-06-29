"""Render atoms to canonical JSON + a derived Obsidian-friendly Markdown view."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ...serialization import serialize_markdown
from .schema import Atom


def render_json(atoms: list[Atom]) -> str:
    return json.dumps([a.to_dict() for a in atoms], ensure_ascii=False, indent=2) + "\n"


def render_markdown(doc_id: str, atoms: list[Atom]) -> str:
    if not atoms:
        return serialize_markdown(f"# Atoms: {doc_id}\n\n_No atoms extracted._")
    lines = [f"# Atoms: {doc_id}", ""]
    by_entity: dict[str, list[Atom]] = defaultdict(list)
    for a in atoms:
        by_entity[a.entity].append(a)
    for ent in sorted(by_entity):
        lines += [f"## [[{ent}]]", ""]
        for a in by_entity[ent]:
            val = a.value if a.value is not None else "[待验证]"
            cond = f" @ {a.condition}" if a.condition else ""
            unit = f" {a.unit}" if a.unit else ""
            lines.append(
                f"- [[{a.parameter}]]: {val}{unit}{cond} "
                f"([{a.section}](main.md#{a.section}))"
            )
        lines.append("")
    return serialize_markdown("\n".join(lines))


def write_atoms(doc_dir: Path, doc_id: str, atoms: list[Atom]) -> None:
    graph = doc_dir / "graph"
    graph.mkdir(parents=True, exist_ok=True)
    (graph / "atoms.json").write_bytes(render_json(atoms).encode("utf-8"))
    (graph / "atoms.md").write_bytes(render_markdown(doc_id, atoms).encode("utf-8"))
