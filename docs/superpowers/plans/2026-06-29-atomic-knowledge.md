# Atomic Knowledge Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `kb wiki atoms` — a per-document LLM layer that extracts minimal, reusable engineering knowledge units (entity/parameter/value/unit/type/condition) into a reproducible `kb/<doc>/graph/atoms.json` plus a derived Obsidian-friendly `atoms.md`.

**Architecture:** Clone of the existing `wiki/requirements` layer. Reuse `sections.iter_content_sections` + `chunk_body`, providers (mock/cached/github-models retry), serialization. New `wiki/atoms/` package: schema, prompts, extractor, render. Atom `id`/`source_doc`/`section`/`evidence_ref` forced by code; missing/uncertain values flagged `待验证`. Deterministic core (adapters/) untouched.

**Tech Stack:** Python 3.11+, Click, uv, pytest (`--disable-socket`), ruff. Spec: `docs/superpowers/specs/2026-06-29-atomic-knowledge-design.md`.

---

## File Structure

- Create `src/kb_extract/wiki/atoms/__init__.py`
- Create `src/kb_extract/wiki/atoms/schema.py` — `Atom` dataclass + `parse_atoms` + `coerce_atom` + `atom_id`
- Create `src/kb_extract/wiki/atoms/assets/base_system_rules.md` (copy), `atoms_rules.md`, `user_template.md`
- Create `src/kb_extract/wiki/atoms/prompts.py`
- Create `src/kb_extract/wiki/atoms/extractor.py`
- Create `src/kb_extract/wiki/atoms/render.py`
- Modify `src/kb_extract/cli.py` — add `wiki atoms` command
- Tests: `tests/test_atoms_schema.py`, `tests/test_atoms_render.py`, `tests/test_atoms_cli.py`
- Version: `pyproject.toml`, `src/kb_extract/__init__.py`, `README.md`, `tests/test_cli.py`, `uv.lock`, `CHANGELOG.md`

---

## Task 1: Atom schema + id + coercion

**Files:**
- Create: `src/kb_extract/wiki/atoms/__init__.py`
- Create: `src/kb_extract/wiki/atoms/schema.py`
- Test: `tests/test_atoms_schema.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_atoms_schema.py
from kb_extract.wiki.atoms.schema import Atom, atom_id, coerce_atom, parse_atoms


def test_atom_id_stable_and_independent_of_value():
    a = atom_id(entity="hinge", parameter="force", condition="open", source_doc="D", section="sec-0001")
    b = atom_id(entity="hinge", parameter="force", condition="open", source_doc="D", section="sec-0001")
    assert a == b and len(a) == 16
    # value is NOT part of identity
    assert a == atom_id(entity="hinge", parameter="force", condition="open", source_doc="D", section="sec-0001")


def test_coerce_forces_source_and_evidence():
    it = coerce_atom({"entity": "Hinge", "parameter": "Force", "value": "5", "unit": "N",
                      "type": "spec", "condition": "open", "source_doc": "LIE", "section": "sec-9"},
                     doc_id="DOC1", anchor="sec-0001")
    assert it.source_doc == "DOC1"
    assert it.section == "sec-0001"
    assert it.evidence_ref == "kb/DOC1/main.md#sec-0001"
    assert it.id == atom_id(entity="hinge", parameter="force", condition="open", source_doc="DOC1", section="sec-0001")


def test_missing_value_flags_pending():
    it = coerce_atom({"entity": "pen", "parameter": "tip force", "type": "requirement"},
                     doc_id="D", anchor="sec-0002")
    assert it.value is None
    assert "待验证" in it.flags


def test_invalid_type_flagged_pending():
    it = coerce_atom({"entity": "x", "parameter": "y", "value": "1", "type": "bogus"},
                     doc_id="D", anchor="sec-1")
    assert it.type == "spec"
    assert "待验证" in it.flags


def test_parse_atoms_strips_fence():
    out = parse_atoms('```json\n[{"entity":"a","parameter":"b"}]\n```')
    assert out == [{"entity": "a", "parameter": "b"}]


def test_to_dict_sorted_flags_and_confidence_rounded():
    it = coerce_atom({"entity": "a", "parameter": "b", "value": "1", "confidence": 0.876},
                     doc_id="D", anchor="sec-1")
    assert it.to_dict()["confidence"] == 0.88
    it2 = Atom(id="x", entity="a", parameter="b", value=None, unit="", type="spec",
               condition="", source_doc="D", section="sec-1",
               evidence_ref="kb/D/main.md#sec-1", confidence=0.5, flags=("z", "a"))
    assert it2.to_dict()["flags"] == ["a", "z"]
```

- [ ] **Step 2: Run, verify fail** — `uv run pytest tests/test_atoms_schema.py -q` -> import error.

- [ ] **Step 3: Implement**

```python
# src/kb_extract/wiki/atoms/__init__.py
"""Atomic knowledge layer (wiki sublayer): schema, prompts, extractor, render."""
```

```python
# src/kb_extract/wiki/atoms/schema.py
"""Atom model + tolerant LLM-JSON parsing/coercion. Source/anchor/id forced."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_VALID_TYPES = ("requirement", "behavior", "constraint", "spec")
PENDING = "待验证"


def atom_id(*, entity: str, parameter: str, condition: str, source_doc: str, section: str) -> str:
    key = "|".join([entity.strip().lower(), parameter.strip().lower(),
                     condition.strip().lower(), source_doc, section])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class Atom:
    id: str
    entity: str
    parameter: str
    value: str | None
    unit: str
    type: str
    condition: str
    source_doc: str
    section: str
    evidence_ref: str
    confidence: float = 0.0
    flags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id, "entity": self.entity, "parameter": self.parameter,
            "value": self.value, "unit": self.unit, "type": self.type,
            "condition": self.condition, "source_doc": self.source_doc,
            "section": self.section, "evidence_ref": self.evidence_ref,
            "confidence": round(self.confidence, 2), "flags": sorted(self.flags),
        }

    def sort_key(self) -> tuple[str, str, str]:
        return (self.section, self.entity, self.id)


def parse_atoms(raw: str) -> list[dict]:
    text = _FENCE_RE.sub("", raw.strip()).strip()
    if not text.startswith("["):
        s, e = text.find("["), text.rfind("]")
        if s < 0 or e < 0 or e < s:
            raise ValueError("LLM response contains no JSON list")
        text = text[s:e + 1]
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("LLM response is not a JSON list")
    return [o for o in data if isinstance(o, dict)]


def coerce_atom(obj: dict, *, doc_id: str, anchor: str) -> Atom:
    def s(k: str) -> str:
        v = obj.get(k)
        return str(v).strip() if v is not None else ""

    flags: list[str] = []
    entity, parameter, condition = s("entity"), s("parameter"), s("condition")
    raw_val = obj.get("value")
    value = str(raw_val).strip() if raw_val is not None and str(raw_val).strip() else None
    if value is None:
        flags.append(PENDING)
    atype = s("type").lower()
    if atype not in _VALID_TYPES:
        atype = "spec"
        flags.append(PENDING)
    try:
        conf = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return Atom(
        id=atom_id(entity=entity, parameter=parameter, condition=condition,
                   source_doc=doc_id, section=anchor),
        entity=entity, parameter=parameter, value=value, unit=s("unit"),
        type=atype, condition=condition, source_doc=doc_id, section=anchor,
        evidence_ref=f"kb/{doc_id}/main.md#{anchor}", confidence=conf,
        flags=tuple(dict.fromkeys(flags)),
    )
```

- [ ] **Step 4: Run, verify pass** — `uv run pytest tests/test_atoms_schema.py -q` -> 6 passed.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "Add Atom schema with forced id/source/evidence and pending flags"`

---

## Task 2: Prompt assets + prompts.py

**Files:**
- Create: `src/kb_extract/wiki/atoms/assets/base_system_rules.md` (copy of requirements asset)
- Create: `src/kb_extract/wiki/atoms/assets/atoms_rules.md`
- Create: `src/kb_extract/wiki/atoms/assets/user_template.md`
- Create: `src/kb_extract/wiki/atoms/prompts.py`
- Test: extend `tests/test_atoms_schema.py`

- [ ] **Step 1: Copy base + write assets** (PowerShell):

```powershell
Copy-Item src\kb_extract\wiki\requirements\assets\base_system_rules.md src\kb_extract\wiki\atoms\assets\base_system_rules.md
```

`atoms_rules.md` content:
```markdown
# Atomic Extraction Rules (P-Atom)

Decompose the section into MINIMAL reusable knowledge units ("atoms"). One atom = one entity's one parameter under one condition.

Each atom is a JSON object: entity, parameter, value, unit, type, condition, confidence.
- type: one of requirement|behavior|constraint|spec
- value: numeric or range string; OMIT or null if not stated. NEVER infer dimensions/force/power.
- confidence: 0..1 self-estimate.
Return ONLY a JSON array. No prose.
```

`user_template.md` content:
```markdown
Extract atoms from this section. Return a JSON array only.

{evidence_content}
```

- [ ] **Step 2: Write failing test**

```python
def test_build_system_prompt_includes_both():
    from kb_extract.wiki.atoms.prompts import build_system_prompt
    p = build_system_prompt()
    assert "Atomic Extraction Rules" in p and len(p) > 200
```

- [ ] **Step 3: Implement** (mirror requirements/prompts.py):

```python
# src/kb_extract/wiki/atoms/prompts.py
from __future__ import annotations
import json
from functools import cache
from pathlib import Path
from ..providers.base import Message
_ASSETS = Path(__file__).with_name("assets")
_SEP = "\n\n---\n\n"

@cache
def _read_asset(rel: str) -> str:
    return (_ASSETS / rel).read_text(encoding="utf-8")

def build_system_prompt() -> str:
    return _SEP.join([_read_asset("base_system_rules.md").rstrip(),
                      _read_asset("atoms_rules.md").rstrip()])

def build_user_prompt(*, anchor: str, section_title: str, section_body: str) -> str:
    ev = json.dumps([{"id": anchor, "type": "text", "section": section_title,
                      "content": section_body}], ensure_ascii=False, indent=2)
    return _read_asset("user_template.md").replace("{evidence_content}", ev)

def compose_messages(*, anchor: str, section_title: str, section_body: str) -> list[Message]:
    return [{"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(anchor=anchor,
             section_title=section_title, section_body=section_body)}]
```

- [ ] **Step 4: Run, verify pass** — `uv run pytest tests/test_atoms_schema.py -q`.
- [ ] **Step 5: Commit** — `git commit -am "Add atoms prompt assets and message composer"`

---

## Task 3: Extractor

**Files:**
- Create: `src/kb_extract/wiki/atoms/extractor.py`
- Test: `tests/test_atoms_cli.py` (extractor covered via CLI in Task 5; add unit here)

- [ ] **Step 1: Write failing test** (add to `tests/test_atoms_schema.py`):

```python
def test_extractor_forces_anchor(tmp_path):
    from kb_extract.wiki.atoms.extractor import extract_atoms
    doc = tmp_path / "kb" / "D"; doc.mkdir(parents=True)
    (doc / "main.md").write_text('<a id="sec-0001"></a>\n# Hinge\n\nForce 5 N.\n', encoding="utf-8")
    class LLM:
        def chat(self, m): return '[{"entity":"hinge","parameter":"force","value":"5","unit":"N","type":"spec"}]'
    r = extract_atoms(tmp_path, LLM())
    assert r.total_atoms == 1
    assert r.atoms_by_doc["D"][0].section == "sec-0001"
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** (clone requirements/extractor.py):

```python
# src/kb_extract/wiki/atoms/extractor.py
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
    def docs(self): return len(self.atoms_by_doc)
    @property
    def total_atoms(self): return sum(len(v) for v in self.atoms_by_doc.values())

def extract_atoms(project_root, llm, *, output_dir=None, max_chars=DEFAULT_MAX_CHARS, dry_run=False):
    kb_root = _kb_dir(project_root, output_dir)
    result = AtomsResult()
    if not kb_root.is_dir():
        return result
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        doc_id = doc_dir.name; atoms: list[Atom] = []
        for sec in iter_content_sections(kb_root, doc_id):
            for chunk in chunk_body(sec.body, max_chars=max_chars):
                msgs = compose_messages(anchor=sec.anchor, section_title=sec.title, section_body=chunk)
                try:
                    raw = llm.chat(msgs)
                    if dry_run:
                        result.ok_sections += 1; continue
                    for obj in parse_atoms(raw):
                        atoms.append(coerce_atom(obj, doc_id=doc_id, anchor=sec.anchor))
                    result.ok_sections += 1
                except Exception:
                    result.failed_sections += 1; continue
        if atoms:
            atoms.sort(key=lambda a: a.sort_key())
            result.atoms_by_doc[doc_id] = atoms
    return result
```

- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "Add atoms extractor reusing section walker"`

---

## Task 4: Render JSON + derived atoms.md

**Files:**
- Create: `src/kb_extract/wiki/atoms/render.py`
- Test: `tests/test_atoms_render.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_atoms_render.py
from kb_extract.wiki.atoms.render import render_json, render_markdown
from kb_extract.wiki.atoms.schema import coerce_atom

def _a(**o): return coerce_atom({"entity": "hinge", "parameter": "force", "value": "5", "unit": "N", "type": "spec", **o}, doc_id="D", anchor="sec-0001")

def test_json_reproducible():
    a = _a()
    assert render_json([a]) == render_json([a])

def test_md_has_wikilinks_and_anchor():
    md = render_markdown("D", [_a()])
    assert "[[hinge]]" in md and "(main.md#sec-0001)" in md

def test_md_marks_pending():
    md = render_markdown("D", [coerce_atom({"entity": "pen", "parameter": "force", "type": "spec"}, doc_id="D", anchor="sec-2")])
    assert "[待验证]" in md
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement**

```python
# src/kb_extract/wiki/atoms/render.py
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
from ...serialization import serialize_markdown
from .schema import Atom, PENDING

def render_json(atoms: list[Atom]) -> str:
    return json.dumps([a.to_dict() for a in atoms], ensure_ascii=False, indent=2) + "\n"

def render_markdown(doc_id: str, atoms: list[Atom]) -> str:
    lines = [f"# Atoms: {doc_id}", ""]
    if not atoms:
        return serialize_markdown("# Atoms: " + doc_id + "\n\n_No atoms extracted._")
    by_entity: dict[str, list[Atom]] = defaultdict(list)
    for a in atoms:
        by_entity[a.entity].append(a)
    for ent in sorted(by_entity):
        lines += [f"## [[{ent}]]", ""]
        for a in by_entity[ent]:
            val = a.value if a.value is not None else "[待验证]"
            cond = f" @ {a.condition}" if a.condition else ""
            lines.append(f"- [[{a.parameter}]]: {val} {a.unit}{cond} "
                         f"([{a.section}](main.md#{a.section}))")
        lines.append("")
    return serialize_markdown("\n".join(lines))

def write_atoms(doc_dir: Path, doc_id: str, atoms: list[Atom]) -> None:
    g = doc_dir / "graph"; g.mkdir(parents=True, exist_ok=True)
    (g / "atoms.json").write_bytes(render_json(atoms).encode("utf-8"))
    (g / "atoms.md").write_bytes(render_markdown(doc_id, atoms).encode("utf-8"))
```

- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "Render atoms.json plus derived Obsidian atoms.md"`

---

## Task 5: CLI command

**Files:**
- Modify: `src/kb_extract/cli.py` (add after `wiki_requirements`, ~line 633)
- Test: `tests/test_atoms_cli.py`

- [ ] **Step 1: Write failing tests** (mirror test_requirements_cli):

```python
# tests/test_atoms_cli.py
import json
from click.testing import CliRunner
from kb_extract.cli import main

def _proj(tmp_path):
    d = tmp_path / "kb" / "DOC1"; d.mkdir(parents=True)
    (d / "main.md").write_text('<a id="sec-0001"></a>\n# Hinge\n\nForce 5 N.\n', encoding="utf-8")
    return tmp_path

def test_atoms_mock_runs(tmp_path):
    r = CliRunner().invoke(main, ["wiki", "atoms", str(_proj(tmp_path))])
    assert r.exit_code == 0 and "wiki atoms:" in r.output

def test_atoms_cached(tmp_path):
    proj = _proj(tmp_path)
    from kb_extract.wiki.providers.cached import prompt_hash
    from kb_extract.wiki.atoms.prompts import compose_messages
    from kb_extract.wiki.requirements.sections import chunk_body, iter_content_sections
    sec = iter_content_sections(proj / "kb", "DOC1")[0]
    chunk = chunk_body(sec.body, max_chars=6000)[0]
    h = prompt_hash(compose_messages(anchor=sec.anchor, section_title=sec.title, section_body=chunk))
    rf = tmp_path / "r.json"; rf.write_text(json.dumps({h: '[{"entity":"hinge","parameter":"force","value":"5","unit":"N","type":"spec"}]'}))
    r = CliRunner().invoke(main, ["wiki", "atoms", str(proj), "--provider", "cached", "--responses-file", str(rf), "--json"])
    assert r.exit_code == 0, r.output
    out = json.loads((proj / "kb" / "DOC1" / "graph" / "atoms.json").read_text(encoding="utf-8"))
    assert out[0]["evidence_ref"] == "kb/DOC1/main.md#sec-0001"
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** — copy `wiki_requirements` command, rename to `atoms`, swap imports to `wiki.atoms.extractor.extract_atoms` / `render.write_atoms`, summary keys `docs/atoms/ok_sections/failed_sections`, echo `wiki atoms: ...`.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "Add kb wiki atoms CLI command"`

---

## Task 6: Version bump + docs

**Files:** `pyproject.toml`, `src/kb_extract/__init__.py`, `README.md`, `tests/test_cli.py`, `CHANGELOG.md`, `uv.lock`

- [ ] **Step 1:** 0.14.0 -> 0.15.0 in pyproject, `__init__`, README badge + `kb --version`, test_cli assert.
- [ ] **Step 2:** README: add 原子知识层 section. CHANGELOG: `## [0.15.0]` 简中 (atom layer, atoms.json + Obsidian atoms.md, 强制 source/anchor, 待验证). `uv lock`.
- [ ] **Step 3:** `uv run pytest -q` (all pass) + `uv run ruff check .` clean.
- [ ] **Step 4: Commit** — `git commit -am "Bump to 0.15.0; document atomic knowledge layer"`

---

## Final: PR
`git push -u origin feat/atomic-knowledge` then create PR; auto-merge squash.
