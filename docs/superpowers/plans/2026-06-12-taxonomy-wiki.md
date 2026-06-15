# Taxonomy Wiki Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize wiki output from flat Jaccard-clustered topics into PRD-driven subsystem folders (~11 categories), with a `taxonomy.json` config file auto-generated from PRD structure.

**Architecture:** New `taxonomy.py` module handles config loading, 4-layer routing engine, and auto-generation from PRD. The orchestrator gains a `taxonomy` parameter; when set, it routes evidence to category folders then sub-clusters within each category. CLI gets `kb wiki taxonomy` subcommand and `--taxonomy` flag on existing commands.

**Tech Stack:** Python 3.11+, Click (CLI), dataclasses, fnmatch (glob matching), json, re. No new dependencies.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/kb_extract/wiki/taxonomy.py` | `Category`, `TaxonomyConfig`, `load_taxonomy`, `save_taxonomy`, `route_evidence`, `build_prd_section_map`, `generate_taxonomy` |
| Create | `tests/test_taxonomy_config.py` | Config load/save/schema validation tests |
| Create | `tests/test_taxonomy_router.py` | `route_evidence` 4-layer priority + PES mapping tests |
| Create | `tests/test_taxonomy_generate.py` | Auto-generation from mock PRD tests |
| Create | `tests/test_wiki_taxonomy_e2e.py` | Orchestrator taxonomy mode + _index.md + verify recursive |
| Modify | `src/kb_extract/wiki/orchestrator.py` | Add taxonomy mode to `build_wiki`, recursive `verify_wiki` |
| Modify | `src/kb_extract/wiki/writer.py` | Category-aware `_build_prompt`, deeper footnote paths |
| Modify | `src/kb_extract/wiki/__init__.py` | Export new symbols |
| Modify | `src/kb_extract/cli.py` | `kb wiki taxonomy` subcommand, `--taxonomy` flag on build/dump-prompts/verify |
| Modify | `pyproject.toml` | Version bump 0.6.0 → 0.7.0 |
| Modify | `src/kb_extract/__init__.py` | Version bump |
| Modify | `CHANGELOG.md` | v0.7.0 entry |

---

### Task 1: TaxonomyConfig data model + load/save

**Files:**
- Create: `src/kb_extract/wiki/taxonomy.py`
- Create: `tests/test_taxonomy_config.py`

- [ ] **Step 1: Write failing tests for TaxonomyConfig**

```python
# tests/test_taxonomy_config.py
"""Taxonomy config data model tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.taxonomy import Category, TaxonomyConfig, load_taxonomy, save_taxonomy

pytestmark = pytest.mark.disable_socket


def test_category_frozen() -> None:
    c = Category(slug="mechanical", title="Mechanical", prd_headings=("Mechanical",),
                 linked_specs=("M9000010*",), keywords=("hinge", "bounce"))
    with pytest.raises(AttributeError):
        c.slug = "other"  # type: ignore[misc]


def test_taxonomy_config_from_dict_roundtrip(tmp_path: Path) -> None:
    cfg = TaxonomyConfig(
        version=1,
        source_prd="BC PRD",
        categories=(
            Category(slug="mechanical", title="Mechanical",
                     prd_headings=("Mechanical",), linked_specs=("M9000010*",),
                     keywords=("hinge",)),
            Category(slug="electrical", title="Electrical",
                     prd_headings=("Electrical",), linked_specs=(),
                     keywords=("power",)),
        ),
    )
    out = tmp_path / "taxonomy.json"
    save_taxonomy(cfg, out)
    loaded = load_taxonomy(out)
    assert loaded == cfg
    assert loaded.version == 1
    assert len(loaded.categories) == 2
    assert loaded.categories[0].slug == "mechanical"


def test_load_taxonomy_rejects_bad_version(tmp_path: Path) -> None:
    p = tmp_path / "taxonomy.json"
    p.write_text(json.dumps({"version": 99, "source_prd": "x", "categories": []}),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_taxonomy(p)


def test_load_taxonomy_rejects_duplicate_slugs(tmp_path: Path) -> None:
    cat = {"slug": "a", "title": "A", "prd_headings": [], "linked_specs": [], "keywords": []}
    p = tmp_path / "taxonomy.json"
    p.write_text(json.dumps({"version": 1, "source_prd": "x", "categories": [cat, cat]}),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_taxonomy(p)


def test_load_taxonomy_rejects_empty_slug(tmp_path: Path) -> None:
    cat = {"slug": "", "title": "A", "prd_headings": [], "linked_specs": [], "keywords": []}
    p = tmp_path / "taxonomy.json"
    p.write_text(json.dumps({"version": 1, "source_prd": "x", "categories": [cat]}),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="slug"):
        load_taxonomy(p)
```

- [ ] **Step 2: Run tests — expect FAIL (module not found)**

Run: `python -m pytest tests/test_taxonomy_config.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement TaxonomyConfig data model + load/save**

```python
# src/kb_extract/wiki/taxonomy.py
"""PRD-driven taxonomy config + routing engine (v0.7.0).

Provides:
- ``Category`` / ``TaxonomyConfig`` data model
- ``load_taxonomy`` / ``save_taxonomy`` — JSON I/O with schema validation (H21)
- ``route_evidence`` — 4-layer priority routing
- ``build_prd_section_map`` — anchor → category from PRD index.json
- ``generate_taxonomy`` — auto-generate taxonomy.json from PRD structure
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass(frozen=True)
class Category:
    slug: str
    title: str
    prd_headings: tuple[str, ...]
    linked_specs: tuple[str, ...]  # glob patterns for doc_id matching
    keywords: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "prd_headings": list(self.prd_headings),
            "linked_specs": list(self.linked_specs),
            "keywords": list(self.keywords),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Category:
        return cls(
            slug=d["slug"],
            title=d["title"],
            prd_headings=tuple(d.get("prd_headings", ())),
            linked_specs=tuple(d.get("linked_specs", ())),
            keywords=tuple(d.get("keywords", ())),
        )


@dataclass(frozen=True)
class TaxonomyConfig:
    version: int  # must be 1
    source_prd: str
    categories: tuple[Category, ...]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "source_prd": self.source_prd,
            "categories": [c.to_dict() for c in self.categories],
        }

    @classmethod
    def from_dict(cls, d: dict) -> TaxonomyConfig:
        return cls(
            version=d["version"],
            source_prd=d["source_prd"],
            categories=tuple(Category.from_dict(c) for c in d.get("categories", ())),
        )


def _validate(cfg: TaxonomyConfig) -> None:
    """Schema validation (H21)."""
    if cfg.version != 1:
        raise ValueError(f"taxonomy.json version must be 1, got {cfg.version}")
    slugs: list[str] = []
    for cat in cfg.categories:
        if not cat.slug or not cat.slug.strip():
            raise ValueError(f"category slug must be non-empty, got {cat.slug!r}")
        if cat.slug in slugs:
            raise ValueError(f"duplicate category slug: {cat.slug!r}")
        slugs.append(cat.slug)


def load_taxonomy(path: Path) -> TaxonomyConfig:
    """Load and validate taxonomy.json."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = TaxonomyConfig.from_dict(raw)
    _validate(cfg)
    return cfg


def save_taxonomy(cfg: TaxonomyConfig, path: Path) -> None:
    """Atomic-write taxonomy.json."""
    _validate(cfg)
    data = (json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="wb", dir=path.parent, delete=False, prefix=".tmp-", suffix=".json") as tmp:
        tmp.write(data)
        tmp_name = tmp.name
    os.replace(tmp_name, path)
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/test_taxonomy_config.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/wiki/taxonomy.py tests/test_taxonomy_config.py
git commit -m "feat(taxonomy): Category + TaxonomyConfig data model with load/save (H21)"
```

---

### Task 2: route_evidence — 4-layer priority routing

**Files:**
- Modify: `src/kb_extract/wiki/taxonomy.py` (add `route_evidence`, `build_prd_section_map`)
- Create: `tests/test_taxonomy_router.py`

- [ ] **Step 1: Write failing tests for route_evidence**

```python
# tests/test_taxonomy_router.py
"""route_evidence 4-layer priority tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.taxonomy import (
    Category,
    TaxonomyConfig,
    build_prd_section_map,
    route_evidence,
)
from kb_extract.wiki.topics import EvidenceRef

pytestmark = pytest.mark.disable_socket

_CFG = TaxonomyConfig(
    version=1,
    source_prd="BC PRD",
    categories=(
        Category(slug="mechanical", title="Mechanical",
                 prd_headings=("Mechanical",),
                 linked_specs=("M9000010*",),
                 keywords=("hinge", "bounce", "stiffness")),
        Category(slug="electrical", title="Electrical",
                 prd_headings=("Electrical",),
                 linked_specs=("M9000011*",),
                 keywords=("power", "voltage", "current")),
        Category(slug="keyboard", title="Keyboard",
                 prd_headings=("Keyset",),
                 linked_specs=("M9000015*",),
                 keywords=("key", "layout", "keycap")),
    ),
)


def _ev(doc_id: str, anchor: str, title: str = "") -> EvidenceRef:
    return EvidenceRef(doc_id=doc_id, anchor=anchor, section_title=title,
                       page_start=1, page_end=1)


# Layer 1: PRD anchor → category via prd_section_map
def test_route_prd_evidence_by_anchor_position() -> None:
    prd_map = {"sec-0010": "mechanical", "sec-0020": "electrical"}
    result = route_evidence(_ev("BC PRD", "sec-0010"), _CFG, prd_map)
    assert result == "mechanical"


def test_route_prd_evidence_by_anchor_electrical() -> None:
    prd_map = {"sec-0010": "mechanical", "sec-0020": "electrical"}
    result = route_evidence(_ev("BC PRD", "sec-0020"), _CFG, prd_map)
    assert result == "electrical"


# Layer 2: linked_specs glob match
def test_route_non_prd_by_linked_specs_glob() -> None:
    result = route_evidence(_ev("M9000010 Rev B", "a1"), _CFG, {})
    assert result == "mechanical"


def test_route_linked_specs_electrical() -> None:
    result = route_evidence(_ev("M9000011 Blade Electrical", "a1"), _CFG, {})
    assert result == "electrical"


# Layer 3: keyword token match
def test_route_by_keyword_fallback() -> None:
    result = route_evidence(_ev("unknown-doc", "a1", "hinge design spec"), _CFG, {})
    assert result == "mechanical"


def test_route_by_keyword_electrical() -> None:
    result = route_evidence(_ev("unknown-doc", "a1", "power supply voltage"), _CFG, {})
    assert result == "electrical"


# Layer 4: _uncategorized fallback
def test_route_uncategorized_when_nothing_matches() -> None:
    result = route_evidence(_ev("random-doc", "a1", "banana smoothie"), _CFG, {})
    assert result == "_uncategorized"


# build_prd_section_map: reads index.json to map anchors to categories
def test_build_prd_section_map(tmp_path: Path) -> None:
    prd_dir = tmp_path / "kb" / "BC PRD"
    prd_dir.mkdir(parents=True)
    index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 99,
        "children": [
            {"node_id": "ch1", "title": "Mechanical", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 10,
             "children": [
                 {"node_id": "s1", "title": "Hinge", "anchor": "sec-0002",
                  "level": 2, "page_start": 2, "page_end": 3, "children": []},
             ]},
            {"node_id": "ch2", "title": "Electrical", "anchor": "sec-0010",
             "level": 1, "page_start": 11, "page_end": 20,
             "children": [
                 {"node_id": "s2", "title": "Power", "anchor": "sec-0011",
                  "level": 2, "page_start": 12, "page_end": 13, "children": []},
             ]},
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    result = build_prd_section_map(tmp_path / "kb", _CFG)
    assert result["sec-0001"] == "mechanical"
    assert result["sec-0002"] == "mechanical"  # child inherits parent category
    assert result["sec-0010"] == "electrical"
    assert result["sec-0011"] == "electrical"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_taxonomy_router.py -v`
Expected: FAIL with `ImportError` (functions not yet defined)

- [ ] **Step 3: Implement route_evidence + build_prd_section_map**

Add to the bottom of `src/kb_extract/wiki/taxonomy.py`:

```python
# --- tokenizer (reuse from topics.py to stay consistent) ---

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "by", "is", "are", "was", "were", "be", "as", "at", "this", "that",
    "it", "from", "into", "about", "introduction", "overview", "appendix",
    "chapter", "section", "part",
    "的", "了", "和", "及", "或", "与", "之", "其", "在", "对", "对于", "关于",
    "概述", "简介", "介绍", "附录", "章", "节", "部分", "总结",
})


def _tokenize(text: str) -> frozenset[str]:
    raw = _TOKEN_RE.findall(text.lower())
    return frozenset(t for t in raw if t and t not in _STOPWORDS and len(t) > 1)


# --- routing engine ---

def route_evidence(
    ev: "EvidenceRef",
    config: TaxonomyConfig,
    prd_section_map: dict[str, str],
) -> str:
    """Route a single evidence ref to a category slug (4-layer priority).

    1. PRD anchor position (if ev.doc_id matches config.source_prd)
    2. linked_specs glob match (fnmatch on ev.doc_id)
    3. keyword token match (intersection with section_title tokens)
    4. ``_uncategorized`` fallback
    """
    # Layer 1: PRD evidence — route by anchor
    if ev.doc_id == config.source_prd and ev.anchor in prd_section_map:
        return prd_section_map[ev.anchor]

    # Layer 2: linked_specs glob match
    for cat in config.categories:
        for pattern in cat.linked_specs:
            if fnmatch(ev.doc_id, pattern):
                return cat.slug

    # Layer 3: keyword token match
    tokens = _tokenize(ev.section_title)
    if tokens:
        best_slug = ""
        best_count = 0
        for cat in config.categories:
            kw_set = frozenset(cat.keywords)
            overlap = len(tokens & kw_set)
            if overlap > best_count:
                best_count = overlap
                best_slug = cat.slug
        if best_count > 0:
            return best_slug

    # Layer 4
    return "_uncategorized"


def build_prd_section_map(
    kb_root: Path,
    config: TaxonomyConfig,
) -> dict[str, str]:
    """Build anchor → category_slug map from PRD index.json.

    Walks the PRD's outline tree. Each top-level child is matched against
    ``config.categories[*].prd_headings`` (case-insensitive substring).
    All descendant anchors inherit the parent's category.
    """
    prd_index = Path(kb_root) / config.source_prd / "index.json"
    if not prd_index.is_file():
        return {}

    root = json.loads(prd_index.read_text(encoding="utf-8"))
    result: dict[str, str] = {}

    def _heading_to_slug(heading: str) -> str:
        """Match heading against category prd_headings (case-insensitive substring)."""
        heading_lower = heading.lower()
        for cat in config.categories:
            for ph in cat.prd_headings:
                if ph.lower() in heading_lower:
                    return cat.slug
        return "_uncategorized"

    def _collect_anchors(node: dict, slug: str) -> None:
        anchor = node.get("anchor", "")
        if anchor:
            result[anchor] = slug
        for child in node.get("children", []):
            _collect_anchors(child, slug)

    for top_child in root.get("children", []):
        title = top_child.get("title", "")
        slug = _heading_to_slug(title)
        _collect_anchors(top_child, slug)

    return result
```

Note: the import for `EvidenceRef` is a string annotation — the actual type is in `topics.py`. We use `from __future__ import annotations` at the top so it's fine.

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/test_taxonomy_router.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/wiki/taxonomy.py tests/test_taxonomy_router.py
git commit -m "feat(taxonomy): route_evidence 4-layer routing + build_prd_section_map"
```

---

### Task 3: generate_taxonomy — auto-generate from PRD

**Files:**
- Modify: `src/kb_extract/wiki/taxonomy.py` (add `generate_taxonomy`)
- Create: `tests/test_taxonomy_generate.py`

- [ ] **Step 1: Write failing tests for generate_taxonomy**

```python
# tests/test_taxonomy_generate.py
"""Auto-generation of taxonomy.json from PRD structure."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.taxonomy import generate_taxonomy

pytestmark = pytest.mark.disable_socket


def _make_prd(kb_root: Path, doc_id: str = "BC PRD") -> Path:
    """Create a minimal PRD with two chapters and a Reference Documents table."""
    prd_dir = kb_root / doc_id
    prd_dir.mkdir(parents=True)

    index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 50,
        "children": [
            {"node_id": "ch1", "title": "Mechanical", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 20,
             "children": [
                 {"node_id": "s1", "title": "Retractable Hinge", "anchor": "sec-0002",
                  "level": 2, "page_start": 2, "page_end": 5, "children": []},
                 {"node_id": "s2", "title": "Flat Bounce", "anchor": "sec-0003",
                  "level": 2, "page_start": 6, "page_end": 10, "children": []},
             ]},
            {"node_id": "ch2", "title": "Electrical", "anchor": "sec-0010",
             "level": 1, "page_start": 21, "page_end": 40,
             "children": [
                 {"node_id": "s3", "title": "Power Draw", "anchor": "sec-0011",
                  "level": 2, "page_start": 22, "page_end": 25, "children": []},
             ]},
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    main_md = (
        '<a id="sec-0001"></a>\n'
        "# Mechanical\n\n"
        "## Reference Documents\n\n"
        "| Document | Number |\n"
        "|---|---|\n"
        "| Keyboard Interface | M9000010 Rev B |\n\n"
        '<a id="sec-0010"></a>\n'
        "# Electrical\n\n"
        "## Reference Documents\n\n"
        "| Document | Number |\n"
        "|---|---|\n"
        "| Blade Electrical | M9000011 |\n"
    )
    (prd_dir / "main.md").write_text(main_md, encoding="utf-8")
    return prd_dir


def test_generate_taxonomy_from_prd(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _make_prd(kb_root)
    cfg = generate_taxonomy(kb_root, prd_doc_id="BC PRD")
    assert cfg.version == 1
    assert cfg.source_prd == "BC PRD"
    slugs = [c.slug for c in cfg.categories]
    assert "mechanical" in slugs
    assert "electrical" in slugs


def test_generate_taxonomy_extracts_linked_specs(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _make_prd(kb_root)
    cfg = generate_taxonomy(kb_root, prd_doc_id="BC PRD")
    mech = next(c for c in cfg.categories if c.slug == "mechanical")
    # Should find M9000010 from Reference Documents table
    assert any("M9000010" in s for s in mech.linked_specs)


def test_generate_taxonomy_generates_keywords_from_subheadings(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _make_prd(kb_root)
    cfg = generate_taxonomy(kb_root, prd_doc_id="BC PRD")
    mech = next(c for c in cfg.categories if c.slug == "mechanical")
    # "retractable" and "hinge" and "bounce" should be in keywords (from sub-headings)
    kw_lower = {k.lower() for k in mech.keywords}
    assert "hinge" in kw_lower or "retractable" in kw_lower


def test_generate_taxonomy_auto_detects_prd(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _make_prd(kb_root, "My Product PRD 1.0")
    cfg = generate_taxonomy(kb_root)  # no prd_doc_id — auto-detect
    assert cfg.source_prd == "My Product PRD 1.0"


def test_generate_taxonomy_raises_when_no_prd(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir(parents=True)
    (kb_root / "some-spec").mkdir()
    (kb_root / "some-spec" / "index.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="PRD"):
        generate_taxonomy(kb_root)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_taxonomy_generate.py -v`
Expected: FAIL with `ImportError` (generate_taxonomy not defined)

- [ ] **Step 3: Implement generate_taxonomy**

Add to the bottom of `src/kb_extract/wiki/taxonomy.py`:

```python
# --- PRD Reference Documents table parser ---

_REF_DOC_RE = re.compile(
    r"\|\s*[^|]+\|\s*((?:M|H)\d{6,}[^|]*)\|",
    re.MULTILINE,
)

_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")


def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = _SLUG_CLEAN_RE.sub("-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unknown"


def _extract_ref_doc_numbers(md_text: str, section_start: int, section_end: int) -> list[str]:
    """Extract M/H document numbers from Reference Documents tables in a range."""
    chunk = md_text[section_start:section_end]
    return [m.group(1).strip().split()[0] for m in _REF_DOC_RE.finditer(chunk)]


def _auto_detect_prd(kb_root: Path) -> str | None:
    """Find PRD doc_id by scanning kb/ folder names."""
    for d in sorted(kb_root.iterdir()):
        if not d.is_dir():
            continue
        name_lower = d.name.lower()
        if "prd" in name_lower or "product requirements" in name_lower:
            if (d / "index.json").is_file():
                return d.name
    return None


def generate_taxonomy(
    kb_root: Path,
    *,
    prd_doc_id: str | None = None,
) -> TaxonomyConfig:
    """Auto-generate TaxonomyConfig from PRD structure.

    1. Find or verify PRD in kb_root
    2. Parse PRD index.json top-level children as categories
    3. Extract Reference Documents from PRD main.md per chapter
    4. Generate keywords from sub-headings
    """
    kb_root = Path(kb_root)
    if prd_doc_id is None:
        prd_doc_id = _auto_detect_prd(kb_root)
    if prd_doc_id is None:
        raise FileNotFoundError(
            f"未找到 PRD 文档。请在 {kb_root} 中放置包含 'PRD' 的文档目录，"
            "或使用 --prd-doc 指定。"
        )

    prd_dir = kb_root / prd_doc_id
    index_path = prd_dir / "index.json"
    main_path = prd_dir / "main.md"

    if not index_path.is_file():
        raise FileNotFoundError(f"PRD index.json 不存在: {index_path}")

    root = json.loads(index_path.read_text(encoding="utf-8"))
    main_md = main_path.read_text(encoding="utf-8") if main_path.is_file() else ""

    top_children = root.get("children", [])
    categories: list[Category] = []

    for i, child in enumerate(top_children):
        title = child.get("title", "").strip()
        if not title:
            continue
        slug = _slugify(title)
        if not slug:
            continue

        # Collect sub-heading titles for keywords
        sub_titles: list[str] = []

        def _collect_titles(node: dict) -> None:
            t = node.get("title", "")
            if t:
                sub_titles.append(t)
            for c in node.get("children", []):
                _collect_titles(c)

        for sub in child.get("children", []):
            _collect_titles(sub)

        keywords = set()
        for st in sub_titles:
            for tok in _tokenize(st):
                keywords.add(tok)

        # Extract reference doc numbers from main.md
        anchor = child.get("anchor", "")
        linked_specs: list[str] = []
        if anchor and main_md:
            needle = f'<a id="{anchor}"></a>'
            start = main_md.find(needle)
            if start >= 0:
                # Find next top-level section anchor
                next_child = top_children[i + 1] if i + 1 < len(top_children) else None
                if next_child:
                    next_anchor = next_child.get("anchor", "")
                    next_needle = f'<a id="{next_anchor}"></a>'
                    end = main_md.find(next_needle, start + 1)
                    if end < 0:
                        end = len(main_md)
                else:
                    end = len(main_md)
                doc_nums = _extract_ref_doc_numbers(main_md, start, end)
                linked_specs = [f"{num}*" for num in doc_nums]

        prd_headings = [title]
        for st in sub_titles:
            prd_headings.append(st)

        categories.append(Category(
            slug=slug,
            title=title,
            prd_headings=tuple(prd_headings),
            linked_specs=tuple(linked_specs),
            keywords=tuple(sorted(keywords)),
        ))

    return TaxonomyConfig(
        version=1,
        source_prd=prd_doc_id,
        categories=tuple(categories),
    )
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/test_taxonomy_generate.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/wiki/taxonomy.py tests/test_taxonomy_generate.py
git commit -m "feat(taxonomy): generate_taxonomy auto-builds config from PRD"
```

---

### Task 4: Orchestrator taxonomy mode

**Files:**
- Modify: `src/kb_extract/wiki/orchestrator.py`
- Modify: `src/kb_extract/wiki/writer.py`
- Create: `tests/test_wiki_taxonomy_e2e.py`

- [ ] **Step 1: Write failing e2e tests for taxonomy build**

```python
# tests/test_wiki_taxonomy_e2e.py
"""Wiki taxonomy mode end-to-end tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki import build_wiki
from kb_extract.wiki.orchestrator import verify_wiki
from kb_extract.wiki.taxonomy import Category, TaxonomyConfig, save_taxonomy

pytestmark = pytest.mark.disable_socket


def _scaffold_taxonomy_kb(root: Path) -> TaxonomyConfig:
    """Create a kb/ with PRD + 2 spec docs, plus a taxonomy.json."""
    kb = root / "kb"

    # PRD
    prd_id = "Test PRD"
    prd_dir = kb / prd_id
    prd_dir.mkdir(parents=True)
    prd_main = (
        '<a id="sec-0001"></a>\n## Mechanical\nMechanical content.\n\n'
        '<a id="sec-0002"></a>\n## Electrical\nElectrical content.\n'
    )
    (prd_dir / "main.md").write_text(prd_main, encoding="utf-8")
    prd_index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 20,
        "children": [
            {"node_id": "ch1", "title": "Mechanical", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 10,
             "children": [
                 {"node_id": "s1a", "title": "Hinge Design", "anchor": "sec-0001a",
                  "level": 2, "page_start": 2, "page_end": 5, "children": []},
                 {"node_id": "s1b", "title": "Bounce Test", "anchor": "sec-0001b",
                  "level": 2, "page_start": 6, "page_end": 8, "children": []},
             ]},
            {"node_id": "ch2", "title": "Electrical", "anchor": "sec-0002",
             "level": 1, "page_start": 11, "page_end": 20,
             "children": [
                 {"node_id": "s2a", "title": "Power Supply", "anchor": "sec-0002a",
                  "level": 2, "page_start": 12, "page_end": 15, "children": []},
             ]},
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(prd_index), encoding="utf-8")

    # Spec doc linked to mechanical
    spec1_id = "M9000010 Interface"
    spec1_dir = kb / spec1_id
    spec1_dir.mkdir(parents=True)
    (spec1_dir / "main.md").write_text(
        '<a id="sec-0001"></a>\n## Connector\nPogo connector spec.\n',
        encoding="utf-8",
    )
    (spec1_dir / "index.json").write_text(json.dumps({
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 5,
        "children": [
            {"node_id": "c1", "title": "Connector Design", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 5, "children": []},
        ],
    }), encoding="utf-8")

    # Taxonomy config
    cfg = TaxonomyConfig(
        version=1,
        source_prd=prd_id,
        categories=(
            Category(slug="mechanical", title="Mechanical",
                     prd_headings=("Mechanical",),
                     linked_specs=("M9000010*",),
                     keywords=("hinge", "bounce", "connector")),
            Category(slug="electrical", title="Electrical",
                     prd_headings=("Electrical",),
                     linked_specs=(),
                     keywords=("power", "voltage")),
        ),
    )
    wiki_dir = root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    save_taxonomy(cfg, wiki_dir / "taxonomy.json")
    return cfg


def test_taxonomy_build_creates_subdirectories(tmp_path: Path) -> None:
    cfg = _scaffold_taxonomy_kb(tmp_path)
    result = build_wiki(tmp_path, provider="mock", seed=0, taxonomy=cfg)
    assert result.ok
    # Check subdirectories exist
    wiki = tmp_path / "wiki"
    assert (wiki / "mechanical").is_dir()
    assert (wiki / "electrical").is_dir()
    # Check _index.md exists
    assert (wiki / "mechanical" / "_index.md").is_file()
    assert (wiki / "electrical" / "_index.md").is_file()


def test_taxonomy_build_evidence_routed_correctly(tmp_path: Path) -> None:
    cfg = _scaffold_taxonomy_kb(tmp_path)
    result = build_wiki(tmp_path, provider="mock", seed=0, taxonomy=cfg)
    # M9000010 evidence should be in mechanical (linked_specs match)
    idx = json.loads((tmp_path / "wiki" / "index.json").read_text(encoding="utf-8"))
    mech_topics = [t for t in idx["topics"] if t.get("category") == "mechanical"]
    assert len(mech_topics) > 0


def test_taxonomy_build_verify_passes(tmp_path: Path) -> None:
    cfg = _scaffold_taxonomy_kb(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=0, taxonomy=cfg)
    violations = verify_wiki(tmp_path)
    assert violations == []


def test_build_without_taxonomy_unchanged(tmp_path: Path) -> None:
    """Without taxonomy param, behavior is flat (backward compat)."""
    _scaffold_taxonomy_kb(tmp_path)
    result = build_wiki(tmp_path, provider="mock", seed=0)
    wiki = tmp_path / "wiki"
    # Should produce flat *.md files, no subdirectories with _index.md
    md_files = list(wiki.glob("*.md"))
    assert len(md_files) > 0


def test_taxonomy_verify_recursive(tmp_path: Path) -> None:
    """verify_wiki should handle wiki/<cat>/<slug>.md (recursive)."""
    cfg = _scaffold_taxonomy_kb(tmp_path)
    build_wiki(tmp_path, provider="mock", seed=0, taxonomy=cfg)
    violations = verify_wiki(tmp_path)
    assert violations == []
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_wiki_taxonomy_e2e.py -v`
Expected: FAIL (build_wiki doesn't accept `taxonomy` param yet)

- [ ] **Step 3: Modify writer.py for taxonomy mode**

In `src/kb_extract/wiki/writer.py`, update `_build_prompt` to accept an optional `category_title` and adjust footnote URL depth:

Replace the `_build_prompt` function:

```python
def _build_prompt(
    topic: Topic,
    kb_root: Path | None = None,
    *,
    category_title: str | None = None,
) -> list[Message]:
    sys_content = (
        "You are summarising technical hardware/firmware specification "
        "documentation. Every factual claim MUST be followed by a citation "
        "of the form [^ev-N] where N indexes the numbered evidence sections "
        "supplied below. Do NOT invent facts; if the evidence is thin, say "
        "so explicitly. Prefer concrete numbers, tolerances, standards "
        "(UL/IEC/MIL/etc), and named components over generalities. Reply in "
        "the same language as the topic title (Chinese title → Chinese body, "
        "English title → English body). Use markdown headings and short "
        "paragraphs. Target 200-400 words. Do NOT add a top-level # heading "
        "(the wrapper supplies one)."
    )
    if category_title:
        sys_content += (
            f"\n\nThis topic belongs to the **{category_title}** subsystem category. "
            "Focus your summary on aspects relevant to this subsystem."
        )
    sys_msg: Message = {"role": "system", "content": sys_content}
    lines = [
        f"Topic: {topic.title}",
        "",
        "Evidence sections (numbered):",
    ]
    for i, ev in enumerate(topic.evidence, start=1):
        page = ""
        if ev.page_start is not None:
            page = f" (p.{ev.page_start})"
        title = ev.section_title[:_MAX_EVIDENCE_CHARS]
        lines.append("")
        lines.append(f"[{i}] {title}{page}  —  source: {ev.doc_id}")
        if kb_root is not None:
            body = read_section_body(kb_root, ev.doc_id, ev.anchor, max_chars=_PER_BODY_CHARS)
            if body:
                lines.append("")
                lines.append("```")
                lines.append(body)
                lines.append("```")
    lines.append("")
    lines.append("Write a 200-400 word wiki entry. Use markdown.")
    user_msg: Message = {"role": "user", "content": "\n".join(lines)}
    return [sys_msg, user_msg]
```

Update `build_topic_markdown` to accept `category_slug` for deeper paths:

```python
def build_topic_markdown(
    topic: Topic,
    llm: LlmClient,
    *,
    kb_root: Path | None = None,
    category_slug: str | None = None,
    category_title: str | None = None,
) -> WikiEntry:
    """Generate a single topic's complete markdown.

    ``category_slug``: when set, footnote URLs are one level deeper:
    ``../../kb/<doc>/main.md#anchor`` instead of ``../kb/<doc>/main.md#anchor``.
    ``category_title``: when set, adds subsystem context to the LLM prompt.
    """
    if not topic.evidence:
        raise ValueError(f"topic {topic.slug} has no evidence")

    messages = _build_prompt(topic, kb_root=kb_root, category_title=category_title)
    body = llm.chat(messages)

    pin_numbers = sorted({int(m.group(1)) for m in _PIN_RE.finditer(body)})
    ev_count = len(topic.evidence)
    unresolved = tuple(n for n in pin_numbers if n < 1 or n > ev_count)

    kb_prefix = "../../kb" if category_slug else "../kb"

    footnote_lines: list[str] = []
    for n in pin_numbers:
        if n < 1 or n > ev_count:
            footnote_lines.append(f"[^ev-{n}]: (UNRESOLVED — evidence index {n} out of range)")
            continue
        ev = topic.evidence[n - 1]
        url = f"{kb_prefix}/{ev.doc_id}/main.md#{ev.anchor}"
        page_hint = ""
        if ev.page_start is not None:
            page_hint = f" (p.{ev.page_start})"
        footnote_lines.append(f"[^ev-{n}]: [{ev.section_title}{page_hint}]({url})")

    md_parts = [
        f"# {topic.title}",
        "",
        f"> Slug: `{topic.slug}` · Evidence sources: {ev_count}",
        "",
        body.strip(),
        "",
    ]
    if footnote_lines:
        md_parts.extend(footnote_lines)
        md_parts.append("")

    return WikiEntry(
        topic_slug=topic.slug,
        markdown="\n".join(md_parts),
        pin_count=len(pin_numbers),
        unresolved_pins=unresolved,
    )
```

- [ ] **Step 4: Modify orchestrator.py for taxonomy mode**

In `src/kb_extract/wiki/orchestrator.py`, update `build_wiki` to accept a `taxonomy` parameter and route evidence into category subdirectories.

Add imports at top:
```python
from .taxonomy import TaxonomyConfig, build_prd_section_map, route_evidence
```

Update `build_wiki` signature and body:

```python
def build_wiki(
    project_root: Path,
    *,
    provider: str | LlmClient = "mock",
    seed: int = 0,
    dry_run: bool = False,
    output_dir: Path | None = None,
    min_evidence: int = 1,
    skip_numeric_titles: bool = False,
    taxonomy: TaxonomyConfig | None = None,
) -> WikiResult:
    """Full wiki rebuild.

    When ``taxonomy`` is provided, evidence is routed to category subdirectories
    using the 4-layer routing engine. Category-internal sub-topics are discovered
    via Jaccard clustering.
    """
    project_root = Path(project_root).resolve()
    if not _kb_dir(project_root, output_dir).is_dir():
        raise FileNotFoundError(
            f"未在 {_kb_dir(project_root, output_dir)} 找到 kb/ 目录；请先运行 `kb extract` 抽取。"
        )

    llm: LlmClient
    if isinstance(provider, str):
        llm = get_provider(provider, seed=seed)
        provider_name = provider
    else:
        llm = provider
        provider_name = getattr(provider, "name", "custom")

    kb_root = _kb_dir(project_root, output_dir)

    if taxonomy is not None:
        return _build_taxonomy_wiki(
            project_root, taxonomy, llm, provider_name, seed, dry_run,
            output_dir, min_evidence, skip_numeric_titles, kb_root,
        )

    # --- flat mode (unchanged) ---
    topics = discover_topics(
        project_root,
        output_dir=output_dir,
        min_evidence=min_evidence,
        skip_numeric_titles=skip_numeric_titles,
    )
    entries = [build_topic_markdown(t, llm, kb_root=kb_root) for t in topics]

    if dry_run:
        return WikiResult(
            project_root=project_root,
            topics=tuple(topics),
            entries=tuple(entries),
            provider_name=provider_name,
            seed=seed,
            unresolved_total=sum(len(e.unresolved_pins) for e in entries),
        )

    wiki_dir = _wiki_dir(project_root, output_dir)
    wiki_dir.mkdir(parents=True, exist_ok=True)

    for old in wiki_dir.glob("*.md"):
        old.unlink()
    idx_path = wiki_dir / "index.json"
    if idx_path.exists():
        idx_path.unlink()

    for topic, entry in zip(topics, entries, strict=True):
        out_path = wiki_dir / f"{topic.slug}.md"
        _atomic_write_bytes(out_path, entry.markdown.encode("utf-8"))

    sha_map = _load_source_sha256_map(project_root, output_dir)
    _atomic_write_bytes(
        idx_path,
        _serialize_index(topics, entries, provider_name, seed, sha_map),
    )

    return WikiResult(
        project_root=project_root,
        topics=tuple(topics),
        entries=tuple(entries),
        provider_name=provider_name,
        seed=seed,
        unresolved_total=sum(len(e.unresolved_pins) for e in entries),
    )
```

Add the new `_build_taxonomy_wiki` function:

```python
def _build_taxonomy_wiki(
    project_root: Path,
    taxonomy: TaxonomyConfig,
    llm: LlmClient,
    provider_name: str,
    seed: int,
    dry_run: bool,
    output_dir: Path | None,
    min_evidence: int,
    skip_numeric_titles: bool,
    kb_root: Path,
) -> WikiResult:
    """Internal: taxonomy-mode wiki build."""
    from collections import defaultdict

    from .topics import EvidenceRef, _is_numeric_title, _tokenize, _walk_index

    # 1. Collect ALL evidence from all docs
    all_evidence: list[EvidenceRef] = []
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        index_file = doc_dir / "index.json"
        if not index_file.is_file():
            continue
        try:
            import json as _json
            root = _json.loads(index_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        pairs: list[tuple[EvidenceRef, frozenset[str]]] = []
        _walk_index(root, doc_dir.name, pairs)
        all_evidence.extend(ev for ev, _ in pairs)

    # 2. Route evidence into categories
    prd_section_map = build_prd_section_map(kb_root, taxonomy)
    cat_evidence: dict[str, list[EvidenceRef]] = defaultdict(list)
    for ev in all_evidence:
        slug = route_evidence(ev, taxonomy, prd_section_map)
        cat_evidence[slug].append(ev)

    # 3. For each category, do Jaccard sub-clustering then build wiki entries
    from .topics import discover_topics as _discover_topics_flat

    all_topics: list[Topic] = []
    all_entries: list[WikiEntry] = []
    cat_slug_to_title = {c.slug: c.title for c in taxonomy.categories}
    cat_slug_to_title["_uncategorized"] = "Uncategorized"

    for cat_slug in sorted(cat_evidence.keys()):
        evs = cat_evidence[cat_slug]
        if not evs:
            continue

        # Filter by min_evidence and skip_numeric_titles at evidence level
        if skip_numeric_titles:
            evs = [e for e in evs if not _is_numeric_title(e.section_title)]
        if not evs:
            continue

        # Sub-cluster within category using Jaccard on section titles
        from .topics import _jaccard_distance, _slugify

        tok_list = [(_tokenize(e.section_title), e) for e in evs]

        # Simple single-linkage clustering (same algo as discover_topics)
        n = len(tok_list)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                if ra < rb:
                    parent[rb] = ra
                else:
                    parent[ra] = rb

        for i in range(n):
            for j in range(i + 1, n):
                if _jaccard_distance(tok_list[i][0], tok_list[j][0]) <= 0.85:
                    union(i, j)

        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(i)

        for root_idx in sorted(clusters.keys()):
            members = sorted(clusters[root_idx])
            cluster_evs = tuple(tok_list[m][1] for m in members)
            if len(cluster_evs) < min_evidence:
                continue

            # Pick title from most-common non-stopword
            from collections import defaultdict as _dd
            word_count: dict[str, int] = _dd(int)
            for m in members:
                for w in tok_list[m][0]:
                    word_count[w] += 1
            if word_count:
                best = sorted(word_count.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            else:
                best = cluster_evs[0].section_title or f"topic-{root_idx}"

            slug = _slugify(best, f"topic-{root_idx:04d}")
            topic = Topic(slug=slug, title=best, evidence=cluster_evs)
            cat_title = cat_slug_to_title.get(cat_slug, cat_slug)
            entry = build_topic_markdown(
                topic, llm, kb_root=kb_root,
                category_slug=cat_slug, category_title=cat_title,
            )
            # Attach category info for serialization
            all_topics.append(topic)
            all_entries.append(entry)

    if dry_run:
        return WikiResult(
            project_root=project_root,
            topics=tuple(all_topics),
            entries=tuple(all_entries),
            provider_name=provider_name,
            seed=seed,
            unresolved_total=sum(len(e.unresolved_pins) for e in all_entries),
        )

    # 4. Write to disk: wiki/<category>/<topic>.md
    wiki_root = _wiki_dir(project_root, output_dir)
    wiki_root.mkdir(parents=True, exist_ok=True)

    # Clean old category subdirs and flat files
    for old in wiki_root.glob("*.md"):
        old.unlink()
    for cat_dir in wiki_root.iterdir():
        if cat_dir.is_dir() and cat_dir.name != "__pycache__":
            import shutil
            shutil.rmtree(cat_dir)
    idx_path = wiki_root / "index.json"
    if idx_path.exists():
        idx_path.unlink()

    # Re-route topics for writing
    topic_cat_map: dict[str, str] = {}
    for ev_list_cat, ev_list in cat_evidence.items():
        for ev in ev_list:
            # We need to map topic → category. Re-derive from evidence routing.
            pass

    # Simpler: re-route each topic's first evidence to determine its category
    for topic in all_topics:
        first_ev = topic.evidence[0]
        cat = route_evidence(first_ev, taxonomy, prd_section_map)
        topic_cat_map[topic.slug] = cat

    # Handle slug collisions within categories
    cat_slug_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    final_topics: list[Topic] = []
    final_entries: list[WikiEntry] = []
    final_cats: list[str] = []

    for topic, entry in zip(all_topics, all_entries, strict=True):
        cat = topic_cat_map.get(topic.slug, "_uncategorized")
        cat_slug_counts[cat][topic.slug] += 1
        count = cat_slug_counts[cat][topic.slug]
        if count > 1:
            new_slug = f"{topic.slug}-{count}"
            topic = Topic(slug=new_slug, title=topic.title, evidence=topic.evidence)
        final_topics.append(topic)
        final_entries.append(entry)
        final_cats.append(cat)

    for topic, entry, cat in zip(final_topics, final_entries, final_cats, strict=True):
        cat_dir = wiki_root / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        out_path = cat_dir / f"{topic.slug}.md"
        _atomic_write_bytes(out_path, entry.markdown.encode("utf-8"))

    # Write _index.md for each category
    for cat_slug_key in sorted(set(final_cats)):
        cat_dir = wiki_root / cat_slug_key
        cat_title = cat_slug_to_title.get(cat_slug_key, cat_slug_key)
        cat_topics = [
            (t, e) for t, e, c in zip(final_topics, final_entries, final_cats, strict=True)
            if c == cat_slug_key
        ]
        index_lines = [
            f"# {cat_title}",
            "",
            f"> {taxonomy.source_prd} — {cat_title} 子系统知识库",
            "",
            "## 文章列表",
            "",
        ]
        for t, _ in sorted(cat_topics, key=lambda x: x[0].slug):
            index_lines.append(f"- [{t.slug}]({t.slug}.md) — {t.title}")
        index_lines.append("")
        _atomic_write_bytes(cat_dir / "_index.md", "\n".join(index_lines).encode("utf-8"))

    # Write index.json (with category field)
    sha_map = _load_source_sha256_map(project_root, output_dir)
    _atomic_write_bytes(
        idx_path,
        _serialize_taxonomy_index(
            final_topics, final_entries, final_cats,
            provider_name, seed, sha_map,
        ),
    )

    return WikiResult(
        project_root=project_root,
        topics=tuple(final_topics),
        entries=tuple(final_entries),
        provider_name=provider_name,
        seed=seed,
        unresolved_total=sum(len(e.unresolved_pins) for e in final_entries),
    )


def _serialize_taxonomy_index(
    topics: list[Topic],
    entries: list[WikiEntry],
    categories: list[str],
    provider_name: str,
    seed: int,
    source_sha_map: dict[str, str] | None = None,
) -> bytes:
    sha_map = source_sha_map or {}
    obj = {
        "schema_version": _WIKI_INDEX_SCHEMA,
        "provider": provider_name,
        "seed": seed,
        "taxonomy_mode": True,
        "topics": [
            {
                "slug": t.slug,
                "title": t.title,
                "category": cat,
                "evidence_count": len(t.evidence),
                "pin_count": e.pin_count,
                "unresolved_pins": list(e.unresolved_pins),
                "evidence_origins": sorted({
                    sha_map[ev.doc_id]
                    for ev in t.evidence
                    if ev.doc_id in sha_map
                }),
                "evidence": [
                    {
                        "doc_id": ev.doc_id,
                        "anchor": ev.anchor,
                        "section_title": ev.section_title,
                        "page_start": ev.page_start,
                        "page_end": ev.page_end,
                    }
                    for ev in t.evidence
                ],
            }
            for t, e, cat in zip(topics, entries, categories, strict=True)
        ],
    }
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
```

- [ ] **Step 5: Update verify_wiki for recursive mode**

In `verify_wiki` in `orchestrator.py`, update to handle both flat and taxonomy (subdirectory) layouts:

```python
def verify_wiki(project_root: Path, output_dir: Path | None = None) -> list[str]:
    """Verify wiki evidence pins resolve to real kb anchors.

    Supports both flat (wiki/*.md) and taxonomy (wiki/<cat>/<slug>.md) layouts.
    """
    project_root = Path(project_root).resolve()
    wiki_root = _wiki_dir(project_root, output_dir)
    kb_root = _kb_dir(project_root, output_dir)
    idx_path = wiki_root / "index.json"
    if not idx_path.is_file():
        return [f"wiki/index.json 不存在于 {wiki_root}"]

    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"wiki/index.json 不是合法 JSON：{e}"]

    is_taxonomy = idx.get("taxonomy_mode", False)
    violations: list[str] = []

    for topic in idx.get("topics", []):
        slug = topic["slug"]
        category = topic.get("category")

        if is_taxonomy and category:
            md_path = wiki_root / category / f"{slug}.md"
            display = f"wiki/{category}/{slug}.md"
        else:
            md_path = wiki_root / f"{slug}.md"
            display = f"wiki/{slug}.md"

        if not md_path.is_file():
            violations.append(f"topic {slug}: {display} 缺失")
            continue
        if topic.get("unresolved_pins"):
            for n in topic["unresolved_pins"]:
                violations.append(f"topic {slug}: evidence pin [^ev-{n}] 越界")

        for ev in topic.get("evidence", []):
            anchor_path = kb_root / ev["doc_id"] / "main.md"
            if not anchor_path.is_file():
                violations.append(
                    f"topic {slug}: 引用文件 kb/{ev['doc_id']}/main.md 不存在"
                )
                continue
            content = anchor_path.read_text(encoding="utf-8")
            needle = f'<a id="{ev["anchor"]}">'
            count = content.count(needle)
            if count == 0:
                violations.append(
                    f"topic {slug}: anchor #{ev['anchor']} 在 kb/{ev['doc_id']}/main.md 中找不到 (H14)"
                )
            elif count > 1:
                violations.append(
                    f"topic {slug}: anchor #{ev['anchor']} 在 kb/{ev['doc_id']}/main.md 中出现了 {count} 次（H17 要求唯一）"
                )

        declared_origins = set(topic.get("evidence_origins", []) or [])
        distinct_doc_ids = {ev["doc_id"] for ev in topic.get("evidence", [])}
        expected_origins = {
            sha
            for did, sha in _load_source_sha256_map(project_root, output_dir).items()
            if did in distinct_doc_ids
        }
        if expected_origins and not expected_origins.issubset(declared_origins):
            missing = sorted(expected_origins - declared_origins)
            violations.append(
                f"topic {slug}: evidence_origins 缺少源 sha256: {missing} (H18)"
            )

    return violations
```

- [ ] **Step 6: Update __init__.py exports**

In `src/kb_extract/wiki/__init__.py`, add taxonomy exports:

```python
from .taxonomy import Category, TaxonomyConfig, load_taxonomy, save_taxonomy

__all__ = [
    "Category",
    "EvidenceRef",
    "LlmClient",
    "Message",
    "TaxonomyConfig",
    "Topic",
    "WikiResult",
    "build_wiki",
    "discover_topics",
    "load_taxonomy",
    "save_taxonomy",
]
```

- [ ] **Step 7: Run tests — expect PASS**

Run: `python -m pytest tests/test_wiki_taxonomy_e2e.py tests/test_taxonomy_config.py tests/test_taxonomy_router.py tests/test_taxonomy_generate.py -v`
Expected: All tests PASS

- [ ] **Step 8: Run full test suite — expect no regressions**

Run: `python -m pytest --tb=short -q`
Expected: All existing 277+ tests PASS plus new tests

- [ ] **Step 9: Commit**

```bash
git add src/kb_extract/wiki/orchestrator.py src/kb_extract/wiki/writer.py \
  src/kb_extract/wiki/__init__.py tests/test_wiki_taxonomy_e2e.py
git commit -m "feat(taxonomy): orchestrator taxonomy mode + recursive verify + category-aware writer"
```

---

### Task 5: CLI — `kb wiki taxonomy` subcommand + `--taxonomy` flag

**Files:**
- Modify: `src/kb_extract/cli.py`

- [ ] **Step 1: Add `kb wiki taxonomy` subcommand**

Add after the `wiki_dump_prompts` function in `cli.py`:

```python
@wiki_group.command(name="taxonomy")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir", "-o", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="从此目录读取 kb/，将 taxonomy.json 写入 wiki/。",
)
@click.option(
    "--prd-doc",
    default=None,
    help="显式指定 PRD 的 doc_id（默认自动检测）。",
)
def wiki_taxonomy_cmd(path: Path, output_dir: Path | None, prd_doc: str | None) -> None:
    """从 PRD 自动生成 taxonomy.json 分类配置。"""
    from .layout import kb_dir as _kb_dir, wiki_dir as _wiki_dir
    from .wiki.taxonomy import generate_taxonomy, save_taxonomy

    if output_dir is not None:
        output_dir = output_dir.resolve()

    kb_root = _kb_dir(path, output_dir)
    if not kb_root.is_dir():
        click.echo(f"kb/ 目录不存在: {kb_root}", err=True)
        sys.exit(1)

    try:
        cfg = generate_taxonomy(kb_root, prd_doc_id=prd_doc)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    out_path = _wiki_dir(path, output_dir) / "taxonomy.json"
    save_taxonomy(cfg, out_path)
    click.echo(
        f"wiki taxonomy: {len(cfg.categories)} categories → {out_path}"
        f" (PRD: {cfg.source_prd})"
    )
    for cat in cfg.categories:
        click.echo(f"  {cat.slug}: {cat.title} ({len(cat.linked_specs)} specs, {len(cat.keywords)} keywords)")

    _record_history(
        path, "wiki taxonomy",
        {"prd_doc": prd_doc, "output_dir": str(output_dir) if output_dir else None},
        0,
        f"categories={len(cfg.categories)}",
    )
```

- [ ] **Step 2: Add `--taxonomy` flag to `wiki build`**

In the `wiki_build` function, add option and logic:

```python
# Add this option to @wiki_group.command(name="build"):
@click.option(
    "--taxonomy",
    is_flag=True,
    help="启用 taxonomy 模式（从 wiki/taxonomy.json 读取分类配置）。",
)
```

Add to the function signature: `taxonomy: bool,`

Add before the `build_wiki` call:

```python
    taxonomy_cfg = None
    if taxonomy:
        from .layout import wiki_dir as _wiki_dir
        from .wiki.taxonomy import load_taxonomy
        tax_path = _wiki_dir(path, output_dir) / "taxonomy.json"
        if not tax_path.is_file():
            raise click.UsageError(
                f"--taxonomy 需要 {tax_path} 存在。请先运行 `kb wiki taxonomy`。"
            )
        taxonomy_cfg = load_taxonomy(tax_path)
```

Pass `taxonomy=taxonomy_cfg` to `build_wiki(...)`.

- [ ] **Step 3: Add `--taxonomy` flag to `wiki dump-prompts`**

Same pattern: add `--taxonomy` flag, load taxonomy.json, pass category info to prompt output.

In `wiki_dump_prompts`, add the option and update the prompt output to include a `category` field when taxonomy is enabled:

```python
@click.option(
    "--taxonomy",
    is_flag=True,
    help="启用 taxonomy 模式，在 prompt 中增加 category 字段。",
)
```

Add to signature: `taxonomy: bool,`

Add logic to route evidence and include category in prompt output:

```python
    if taxonomy:
        from .layout import wiki_dir as _wiki_dir
        from .wiki.taxonomy import (
            build_prd_section_map,
            load_taxonomy,
            route_evidence as _route,
        )
        tax_path = _wiki_dir(path, output_dir) / "taxonomy.json"
        if not tax_path.is_file():
            raise click.UsageError(f"--taxonomy 需要 {tax_path}。")
        tax_cfg = load_taxonomy(tax_path)
        prd_map = build_prd_section_map(kb_root, tax_cfg)
        for h, entry in prompts.items():
            # Determine category from first evidence
            topic = next(t for t in topics if t.slug == entry["topic_slug"])
            cat = _route(topic.evidence[0], tax_cfg, prd_map)
            entry["category"] = cat
```

- [ ] **Step 4: Run CLI smoke test**

Run: `python -m kb_extract --version`
Expected: version output, no import errors

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/cli.py
git commit -m "feat(cli): kb wiki taxonomy subcommand + --taxonomy flag on build/dump-prompts"
```

---

### Task 6: Version bump + CHANGELOG + full suite

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/kb_extract/__init__.py`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_cli.py` (version string)

- [ ] **Step 1: Bump version to 0.7.0**

In `pyproject.toml`: change `version = "0.6.0"` to `version = "0.7.0"`
In `src/kb_extract/__init__.py`: change `__version__ = "0.6.0"` to `__version__ = "0.7.0"`
In `tests/test_cli.py`: update version assertion from `"0.6.0"` to `"0.7.0"`

Check for other version references:
```bash
grep -r "0\.6\.0" --include="*.py" --include="*.json" --include="*.toml" --include="*.md" src/ tests/ plugin.json marketplace.json
```

Update any found in `plugin.json`, `marketplace.json`, `README.md`.

- [ ] **Step 2: Add CHANGELOG entry**

Add to top of `CHANGELOG.md` (after any header):

```markdown
## [0.7.0] — 2026-06-xx

### Added
- `kb wiki taxonomy <src> -o <out>` — 从 PRD 自动生成 taxonomy.json 分类配置
- `--taxonomy` flag on `kb wiki build` — 启用 taxonomy 模式，按子系统文件夹组织 wiki
- `--taxonomy` flag on `kb wiki dump-prompts` — prompts 输出中增加 category 字段
- `TaxonomyConfig` / `Category` 数据模型 + JSON schema 校验 (H21)
- 4 层路由引擎：PRD 锚点 → linked_specs glob → keywords token → _uncategorized
- `_index.md` 自动生成每个 category 的概览页
- `verify_wiki` 支持递归 `wiki/<category>/<slug>.md` 结构

### Changed
- writer.py: prompt 支持 category 上下文 + 更深的 footnote 路径 `../../kb/`
- orchestrator.py: `build_wiki` 新增 `taxonomy` 参数
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest --tb=short -q`
Expected: All tests PASS (277 existing + ~26 new)

- [ ] **Step 4: Run ruff**

Run: `python -m ruff check src/ tests/`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: version bump 0.7.0 + CHANGELOG"
```

---

### Task 7: Real-data test on BC dataset

**Files:** No source changes. Run commands on real data.

- [ ] **Step 1: Generate taxonomy.json from BC PRD**

```powershell
$env:PYTHONIOENCODING = "utf-8"
$src = 'C:\Users\xumax\AI Project\Private\BUR-K\spppeeeeccc'
$out = 'C:\Users\xumax\AI Project\Private\markdown\k-bur'

kb wiki taxonomy $src -o $out
```

Expected: taxonomy.json written with ~10-15 categories, PRD auto-detected.

- [ ] **Step 2: Review and hand-edit taxonomy.json if needed**

Open `$out/wiki/taxonomy.json`, verify:
- Categories match PRD chapters
- linked_specs patterns look correct
- Keywords are reasonable

Hand-edit if needed (add PES section mapping, adjust keywords).

- [ ] **Step 3: Dump prompts in taxonomy mode**

```powershell
kb wiki dump-prompts $src -o $out --out "$out\prompts-taxonomy.json" `
  --min-evidence 2 --skip-numeric-titles --taxonomy
```

Expected: prompts with `category` field per topic.

- [ ] **Step 4: Build wiki in taxonomy mode (mock provider for structure test)**

```powershell
kb wiki build $src -o $out --provider mock --taxonomy `
  --min-evidence 2 --skip-numeric-titles
```

Expected: wiki/ now has subdirectories (mechanical/, electrical/, etc.) with _index.md files.

- [ ] **Step 5: Verify**

```powershell
kb wiki verify $src -o $out
```

Expected: `wiki verify: ok`

- [ ] **Step 6: Generate real LLM responses (using cached provider workflow)**

Use `build_responses.py` pattern to fill `responses-taxonomy.json` from the taxonomy-mode prompts, then:

```powershell
kb wiki build $src -o $out --provider cached `
  --responses-file "$out\responses-taxonomy.json" `
  --taxonomy --min-evidence 2 --skip-numeric-titles
```

- [ ] **Step 7: Final verify**

```powershell
kb wiki verify $src -o $out
```

Expected: `wiki verify: ok`

---

### Task 8: PR + CI + merge + tag

**Files:** No source changes.

- [ ] **Step 1: Create feature branch and push**

```bash
git checkout -b feat/taxonomy-wiki
git push -u origin feat/taxonomy-wiki
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --title "feat(wiki): PRD-driven taxonomy wiki (v0.7.0)" \
  --body "Adds taxonomy routing engine, `kb wiki taxonomy` command, `--taxonomy` flag.
See docs/superpowers/specs/2026-06-12-taxonomy-wiki-design.md for design."
```

- [ ] **Step 3: Wait for CI**

All 8 checks should pass (ubuntu/windows/macos × py3.11/3.12 + H13 + perf).

- [ ] **Step 4: Squash merge**

```bash
gh pr merge --squash --delete-branch
```

- [ ] **Step 5: Tag**

```bash
git checkout main && git pull
git tag v0.7.0 && git push origin v0.7.0
```
