"""Orchestrate atom extraction over a kb/ tree (wiki layer).

Reuses the requirements section walker + chunker. Per-chunk failures are
isolated. Atom id/source/anchor/evidence are forced by code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...layout import kb_dir as _kb_dir
from ..providers.base import LlmClient
from ..requirements.sections import chunk_body, iter_content_sections
from .prompts import compose_messages
from .schema import Atom, coerce_atom, parse_atoms

DEFAULT_MAX_CHARS = 6000


@dataclass(slots=True)
class AtomsResult:
    atoms_by_doc: dict[str, list[Atom]] = field(default_factory=dict)
    ok_sections: int = 0
    failed_sections: int = 0

    @property
    def docs(self) -> int:
        return len(self.atoms_by_doc)

    @property
    def total_atoms(self) -> int:
        return sum(len(v) for v in self.atoms_by_doc.values())


def extract_atoms(
    project_root: Path,
    llm: LlmClient,
    *,
    output_dir: Path | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    dry_run: bool = False,
) -> AtomsResult:
    kb_root = _kb_dir(project_root, output_dir)
    result = AtomsResult()
    if not kb_root.is_dir():
        return result

    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        doc_id = doc_dir.name
        atoms: list[Atom] = []
        for sec in iter_content_sections(kb_root, doc_id):
            for chunk in chunk_body(sec.body, max_chars=max_chars):
                messages = compose_messages(
                    anchor=sec.anchor, section_title=sec.title, section_body=chunk
                )
                try:
                    raw = llm.chat(messages)
                    if dry_run:
                        result.ok_sections += 1
                        continue
                    for obj in parse_atoms(raw):
                        atoms.append(coerce_atom(obj, doc_id=doc_id, anchor=sec.anchor))
                    result.ok_sections += 1
                except Exception:
                    result.failed_sections += 1
                    continue
        if atoms:
            atoms.sort(key=lambda a: a.sort_key())
            result.atoms_by_doc[doc_id] = atoms
    return result
