"""Render module assignment to modules.json + per-module Markdown pages."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ...serialization import serialize_markdown
from ..atoms.schema import Atom
from .rules import ModuleRules


def render_modules_json(buckets: dict[str, list[str]], pending: list[str]) -> str:
    payload = {m: sorted(ids) for m, ids in buckets.items()}
    payload["_pending"] = sorted(pending)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_module_page(
    module: str, atom_ids: set[str], atoms: list[Atom], entity_modules: dict[str, set[str]]
) -> str:
    mine = [a for a in atoms if a.id in atom_ids]
    if not mine:
        return serialize_markdown(f"# {module}\n\n_No atoms in this module._")
    by_entity: dict[str, list[Atom]] = defaultdict(list)
    for a in mine:
        by_entity[a.entity].append(a)
    lines = [f"# {module}", ""]
    see_also: set[str] = set()
    for ent in sorted(by_entity):
        lines += [f"## [[{ent}]]", ""]
        for a in by_entity[ent]:
            val = a.value if a.value is not None else "[待验证]"
            unit = f" {a.unit}" if a.unit else ""
            cond = f" @ {a.condition}" if a.condition else ""
            lines.append(
                f"- [[{a.parameter}]]: {val}{unit}{cond} "
                f"([{a.section}](../main.md#{a.section}))"
            )
        see_also |= {m for m in entity_modules.get(ent, set()) if m != module}
        lines.append("")
    if see_also:
        lines += ["## See also", "", "".join(f"- [[{m}]]\n" for m in sorted(see_also))]
    return serialize_markdown("\n".join(lines))


def write_modules(
    doc_dir: Path, doc_id: str, atoms: list[Atom], buckets: dict[str, list[str]],
    pending: list[str], rules: ModuleRules,
) -> None:
    graph = doc_dir / "graph"
    mdir = graph / "modules"
    mdir.mkdir(parents=True, exist_ok=True)
    (graph / "modules.json").write_bytes(
        render_modules_json(buckets, pending).encode("utf-8")
    )
    entity_modules: dict[str, set[str]] = defaultdict(set)
    by_id = {a.id: a for a in atoms}
    for module, ids in buckets.items():
        for i in ids:
            if i in by_id:
                entity_modules[by_id[i].entity].add(module)
    for module in rules.modules:
        page = render_module_page(module, set(buckets[module]), atoms, entity_modules)
        fname = module.replace("/", "-").replace(" ", "_") + ".md"
        (mdir / fname).write_bytes(page.encode("utf-8"))
