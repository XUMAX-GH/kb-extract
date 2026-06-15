"""PRD-driven taxonomy config + routing engine (v0.7.0).

Provides:
- ``Category`` / ``TaxonomyConfig`` data model
- ``load_taxonomy`` / ``save_taxonomy`` — JSON I/O with schema validation (H21)
- ``route_evidence`` — 4-layer priority routing (Task 2)
- ``build_prd_section_map`` — anchor → category from PRD index.json (Task 2)
- ``generate_taxonomy`` — auto-generate taxonomy.json from PRD structure (Task 3)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .topics import EvidenceRef


@dataclass(frozen=True, slots=True)
class Category:
    slug: str
    title: str
    prd_headings: tuple[str, ...]
    linked_specs: tuple[str, ...]
    keywords: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "slug": self.slug,
            "title": self.title,
            "prd_headings": list(self.prd_headings),
            "linked_specs": list(self.linked_specs),
            "keywords": list(self.keywords),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Category:
        return cls(
            slug=str(data["slug"]),
            title=str(data["title"]),
            prd_headings=tuple(str(item) for item in data.get("prd_headings", ())),
            linked_specs=tuple(str(item) for item in data.get("linked_specs", ())),
            keywords=tuple(str(item) for item in data.get("keywords", ())),
        )


@dataclass(frozen=True, slots=True)
class CategoryNode:
    """Hierarchical taxonomy v2 node (spec 2026-06-15).

    A CategoryNode represents one layer in the system -> subsystem ->
    part -> function tree. Children must use a strictly descending layer.
    Designed to coexist with the v1 ``Category`` class during the v0.9.0
    migration; v1 is retained for backwards compatibility until PR-B
    switches all callers over.
    """
    slug: str
    title: str
    layer: str  # "system" | "subsystem" | "part" | "function"
    prd_headings: tuple[str, ...] = ()
    pes_headings: tuple[str, ...] = ()
    linked_specs: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    children: tuple[CategoryNode, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "slug": self.slug,
            "title": self.title,
            "layer": self.layer,
            "prd_headings": list(self.prd_headings),
            "pes_headings": list(self.pes_headings),
            "linked_specs": list(self.linked_specs),
            "keywords": list(self.keywords),
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> CategoryNode:
        raw_children = data.get("children", ())
        children: tuple[CategoryNode, ...] = ()
        if isinstance(raw_children, list):
            children = tuple(
                cls.from_dict(c) for c in raw_children if isinstance(c, dict)
            )
        return cls(
            slug=str(data["slug"]),
            title=str(data["title"]),
            layer=str(data["layer"]),
            prd_headings=tuple(str(item) for item in data.get("prd_headings", ())),
            pes_headings=tuple(str(item) for item in data.get("pes_headings", ())),
            linked_specs=tuple(str(item) for item in data.get("linked_specs", ())),
            keywords=tuple(str(item) for item in data.get("keywords", ())),
            children=children,
        )


@dataclass(frozen=True, slots=True)
class TaxonomyConfig:
    version: int
    source_prd: str
    categories: tuple[Category, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "source_prd": self.source_prd,
            "categories": [category.to_dict() for category in self.categories],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TaxonomyConfig:
        return cls(
            version=int(data["version"]),
            source_prd=str(data["source_prd"]),
            categories=tuple(
                Category.from_dict(category) for category in data.get("categories", ())
            ),
        )


def _validate(cfg: TaxonomyConfig) -> None:
    """Validate the supported taxonomy schema."""
    if cfg.version != 1:
        raise ValueError(f"taxonomy.json version must be 1, got {cfg.version}")

    seen_slugs: set[str] = set()
    for category in cfg.categories:
        if not category.slug.strip():
            raise ValueError(
                f"category slug must be non-empty, got {category.slug!r}"
            )
        if category.slug in seen_slugs:
            raise ValueError(f"duplicate category slug: {category.slug!r}")
        seen_slugs.add(category.slug)


def load_taxonomy(path: Path) -> TaxonomyConfig:
    """Load and validate taxonomy.json."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = TaxonomyConfig.from_dict(raw)
    _validate(cfg)
    return cfg


def save_taxonomy(cfg: TaxonomyConfig, path: Path) -> None:
    """Write taxonomy.json atomically."""
    _validate(cfg)
    data = (
        json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="wb", dir=path.parent, delete=False, prefix=".tmp-", suffix=".json"
    ) as tmp:
        tmp.write(data)
        tmp_name = tmp.name
    os.replace(tmp_name, path)


_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "as",
        "at",
        "this",
        "that",
        "it",
        "from",
        "into",
        "about",
        "introduction",
        "overview",
        "appendix",
        "chapter",
        "section",
        "part",
        "的",
        "了",
        "和",
        "及",
        "或",
        "与",
        "之",
        "其",
        "在",
        "对",
        "对于",
        "关于",
        "概述",
        "简介",
        "介绍",
        "附录",
        "章",
        "节",
        "部分",
        "总结",
    }
)


def _tokenize(text: str) -> frozenset[str]:
    raw = _TOKEN_RE.findall(text.lower())
    return frozenset(
        token for token in raw if token and token not in _STOPWORDS and len(token) > 1
    )


def _keyword_tokens(keywords: tuple[str, ...]) -> frozenset[str]:
    return frozenset(token for keyword in keywords for token in _tokenize(keyword))


def _matches_linked_spec(doc_id: str, pattern: str) -> bool:
    return fnmatchcase(doc_id.lower(), pattern.lower())


def _normalize_doc_id(doc_id: str) -> str:
    return doc_id.strip().lower()


def _resolve_child_casefold(parent: Path, name: str) -> Path | None:
    target = name.lower()
    for child in parent.iterdir():
        if child.name.lower() == target:
            return child
    return None


def route_evidence(
    ev: EvidenceRef,
    config: TaxonomyConfig,
    prd_section_map: dict[str, str],
) -> str:
    """Route a single evidence ref to a category slug."""
    if _normalize_doc_id(ev.doc_id) == _normalize_doc_id(config.source_prd):
        mapped_slug = prd_section_map.get(ev.anchor, "")
        if mapped_slug:
            return mapped_slug
    else:
        for cat in config.categories:
            for pattern in cat.linked_specs:
                if _matches_linked_spec(ev.doc_id, pattern):
                    return cat.slug

    tokens = _tokenize(ev.section_title)
    if tokens:
        best_slug = ""
        best_count = 0
        for cat in config.categories:
            overlap = len(tokens & _keyword_tokens(cat.keywords))
            if overlap > best_count:
                best_count = overlap
                best_slug = cat.slug
        if best_count > 0:
            return best_slug

    return "_uncategorized"


def build_prd_section_map(
    kb_root: Path,
    config: TaxonomyConfig,
) -> dict[str, str]:
    """Build anchor -> category_slug map from a PRD index.json tree."""
    kb_root = Path(kb_root)
    prd_dir = _resolve_child_casefold(kb_root, config.source_prd)
    if prd_dir is None:
        return {}
    prd_index = prd_dir / "index.json"
    if not prd_index.is_file():
        return {}

    root = json.loads(prd_index.read_text(encoding="utf-8"))
    result: dict[str, str] = {}

    def _heading_to_slug(heading: str) -> str:
        heading_lower = heading.lower()
        for cat in config.categories:
            for prd_heading in cat.prd_headings:
                if prd_heading.lower() in heading_lower:
                    return cat.slug
        return ""

    def _collect_anchors(node: dict[str, object], slug: str) -> None:
        anchor = str(node.get("anchor", ""))
        if anchor:
            result[anchor] = slug
        children = node.get("children", [])
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    _collect_anchors(child, slug)

    children = root.get("children", [])
    if isinstance(children, list):
        for top_child in children:
            if not isinstance(top_child, dict):
                continue
            slug = _heading_to_slug(str(top_child.get("title", "")))
            if not slug:
                continue
            _collect_anchors(top_child, slug)

    return result


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
        if (
            ("prd" in name_lower or "product requirements" in name_lower)
            and (d / "index.json").is_file()
        ):
            return d.name
    return None


def generate_taxonomy(
    kb_root: Path,
    *,
    prd_doc_id: str | None = None,
) -> TaxonomyConfig:
    """Auto-generate TaxonomyConfig from PRD structure."""
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
        if not isinstance(child, dict):
            continue

        title = str(child.get("title", "")).strip()
        if not title:
            continue
        slug = _slugify(title)
        if not slug:
            continue

        sub_titles: list[str] = []
        children = child.get("children", [])
        if isinstance(children, list):
            for sub in children:
                if not isinstance(sub, dict):
                    continue
                stack = [sub]
                while stack:
                    node = stack.pop()
                    t = str(node.get("title", "")).strip()
                    if t:
                        sub_titles.append(t)
                    descendants = node.get("children", [])
                    if isinstance(descendants, list):
                        for descendant in reversed(descendants):
                            if isinstance(descendant, dict):
                                stack.append(descendant)

        keywords: set[str] = set()
        for st in sub_titles:
            keywords.update(_tokenize(st))

        anchor = str(child.get("anchor", "")).strip()
        linked_specs: list[str] = []
        if anchor and main_md:
            needle = f'<a id="{anchor}"></a>'
            start = main_md.find(needle)
            if start >= 0:
                next_child = top_children[i + 1] if i + 1 < len(top_children) else None
                if isinstance(next_child, dict):
                    next_anchor = str(next_child.get("anchor", "")).strip()
                    next_needle = f'<a id="{next_anchor}"></a>'
                    end = main_md.find(next_needle, start + 1) if next_anchor else -1
                    if end < 0:
                        end = len(main_md)
                else:
                    end = len(main_md)
                doc_nums = _extract_ref_doc_numbers(main_md, start, end)
                linked_specs = [f"{num}*" for num in doc_nums]

        prd_headings = [title, *sub_titles]
        categories.append(
            Category(
                slug=slug,
                title=title,
                prd_headings=tuple(prd_headings),
                linked_specs=tuple(linked_specs),
                keywords=tuple(sorted(keywords)),
            )
        )

    return TaxonomyConfig(
        version=1,
        source_prd=prd_doc_id,
        categories=tuple(categories),
    )


# ---------------------------------------------------------------------------
# Hierarchical Taxonomy v2 (PR-A: data model + schema migrate + H21)
# Spec: docs/superpowers/specs/2026-06-15-taxonomy-v2-design.md
# ---------------------------------------------------------------------------

_VALID_LAYERS: tuple[str, ...] = ("system", "subsystem", "part", "function")
_LAYER_INDEX: dict[str, int] = {name: i for i, name in enumerate(_VALID_LAYERS)}


@dataclass(frozen=True, slots=True)
class TaxonomyConfigV2:
    """Hierarchical taxonomy root (schema v2).

    ``source_pes_glob`` is the fnmatch pattern used to enumerate PES
    documents at generation time, kept for reproducibility. ``None``
    means PES mounting was not performed (flat PRD-only generation).
    """
    version: int
    source_prd: str
    source_pes_glob: str | None
    categories: tuple[CategoryNode, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "source_prd": self.source_prd,
            "source_pes_glob": self.source_pes_glob,
            "categories": [cat.to_dict() for cat in self.categories],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TaxonomyConfigV2:
        raw_cats = data.get("categories", ())
        cats: tuple[CategoryNode, ...] = ()
        if isinstance(raw_cats, list):
            cats = tuple(
                CategoryNode.from_dict(c) for c in raw_cats if isinstance(c, dict)
            )
        glob_val = data.get("source_pes_glob")
        return cls(
            version=int(data["version"]),
            source_prd=str(data["source_prd"]),
            source_pes_glob=None if glob_val is None else str(glob_val),
            categories=cats,
        )


def migrate_v1_to_v2(raw: dict) -> dict:
    """Transparent migrator from schema v1 to v2.

    Idempotent: v2 input is returned untouched. Every v1 category is
    promoted to a layer="system" CategoryNode with empty
    ``children`` / ``pes_headings``; ``source_pes_glob`` defaults to
    ``None`` to signal PES mounting was never performed.
    """
    version = int(raw.get("version", 1))
    if version >= 2:
        return raw
    return {
        "version": 2,
        "source_prd": raw.get("source_prd", ""),
        "source_pes_glob": None,
        "categories": [
            {
                "slug": cat.get("slug", ""),
                "title": cat.get("title", ""),
                "layer": "system",
                "prd_headings": list(cat.get("prd_headings", [])),
                "pes_headings": [],
                "linked_specs": list(cat.get("linked_specs", [])),
                "keywords": list(cat.get("keywords", [])),
                "children": [],
            }
            for cat in raw.get("categories", [])
            if isinstance(cat, dict)
        ],
    }


def load_taxonomy_v2(path: Path) -> TaxonomyConfigV2:
    """Load taxonomy.json, transparently migrating v1 -> v2 if needed.

    Validation is run before return so callers always get a config that
    satisfies H21.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = migrate_v1_to_v2(raw)
    cfg = TaxonomyConfigV2.from_dict(raw)
    validate_taxonomy_v2(cfg)
    return cfg


def save_taxonomy_v2(cfg: TaxonomyConfigV2, path: Path) -> None:
    """Write taxonomy.json atomically (deterministic bytes)."""
    validate_taxonomy_v2(cfg)
    data = (
        json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="wb", dir=path.parent, delete=False, prefix=".tmp-", suffix=".json"
    ) as tmp:
        tmp.write(data)
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def validate_taxonomy_v2(cfg: TaxonomyConfigV2) -> None:
    """H21 v2: validate hierarchical taxonomy invariants.

    Raises :class:`HardnessViolation` with ``invariant="H21"`` on:
      - wrong schema version
      - empty slug
      - duplicate sibling slugs in same namespace
      - unknown layer name
      - layer that is not strictly descending from its parent
      - tree depth > 4
    """
    from ..errors import HardnessViolation

    if cfg.version != 2:
        raise HardnessViolation(
            invariant="H21",
            detail=f"TaxonomyConfigV2.version must be 2, got {cfg.version}",
        )

    def walk(nodes: tuple[CategoryNode, ...], parent_layer_idx: int,
             depth: int, path_breadcrumb: str) -> None:
        if not nodes:
            return
        if depth > 4:
            raise HardnessViolation(
                invariant="H21",
                detail=f"taxonomy depth exceeds 4 at {path_breadcrumb!r}",
            )
        seen: set[str] = set()
        for node in nodes:
            if not node.slug.strip():
                raise HardnessViolation(
                    invariant="H21",
                    detail=f"empty slug at {path_breadcrumb!r}",
                )
            if node.slug in seen:
                raise HardnessViolation(
                    invariant="H21",
                    detail=(
                        f"duplicate sibling slug {node.slug!r} under "
                        f"{path_breadcrumb!r}"
                    ),
                )
            seen.add(node.slug)
            if node.layer not in _LAYER_INDEX:
                raise HardnessViolation(
                    invariant="H21",
                    detail=(
                        f"unknown layer {node.layer!r} at "
                        f"{path_breadcrumb}/{node.slug}; expected one of "
                        f"{_VALID_LAYERS}"
                    ),
                )
            node_idx = _LAYER_INDEX[node.layer]
            if node_idx != parent_layer_idx + 1:
                raise HardnessViolation(
                    invariant="H21",
                    detail=(
                        f"layer {node.layer!r} at {path_breadcrumb}/{node.slug} "
                        f"must be exactly one level deeper than parent "
                        f"({_VALID_LAYERS[parent_layer_idx] if parent_layer_idx >= 0 else 'root'})"
                    ),
                )
            walk(node.children, node_idx, depth + 1,
                 f"{path_breadcrumb}/{node.slug}")

    walk(cfg.categories, parent_layer_idx=-1, depth=1, path_breadcrumb="")
