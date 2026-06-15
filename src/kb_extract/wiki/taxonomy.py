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


# ---------------------------------------------------------------------------
# Hierarchical Taxonomy v2 (PR-B: generator + routing)
# ---------------------------------------------------------------------------


def _walk_tree_titles(node: dict) -> list[str]:
    """Flatten all descendant titles (depth-first) for keyword extraction."""
    out: list[str] = []
    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict):
                continue
            t = str(child.get("title", "")).strip()
            if t:
                out.append(t)
            out.extend(_walk_tree_titles(child))
    return out


def _extract_subsystem_linked_specs(
    main_md: str, anchor: str, next_anchor: str | None,
) -> list[str]:
    """Return linked spec patterns ('M123456*') found in [anchor, next_anchor)."""
    if not anchor or not main_md:
        return []
    needle = f'<a id="{anchor}"></a>'
    start = main_md.find(needle)
    if start < 0:
        return []
    if next_anchor:
        end = main_md.find(f'<a id="{next_anchor}"></a>', start + 1)
        if end < 0:
            end = len(main_md)
    else:
        end = len(main_md)
    nums = _extract_ref_doc_numbers(main_md, start, end)
    return [f"{num}*" for num in nums]


def _collect_anchor_pairs(top_children: list[dict]) -> list[tuple[str, str | None]]:
    """Return [(anchor, next_anchor_or_None), ...] in document order."""
    anchors = [str(c.get("anchor", "")).strip() for c in top_children
               if isinstance(c, dict)]
    return [(a, anchors[i + 1] if i + 1 < len(anchors) else None)
            for i, a in enumerate(anchors)]


def _discover_pes_docs(kb_root: Path, pes_glob: str,
                       prd_doc_id: str) -> list[str]:
    """Find PES document directories matching pes_glob (excluding the PRD)."""
    matches: list[str] = []
    for d in sorted(kb_root.iterdir()):
        if not d.is_dir() or d.name == prd_doc_id:
            continue
        if not (d / "index.json").is_file():
            continue
        if fnmatchcase(d.name, pes_glob):
            matches.append(d.name)
    return matches


def generate_taxonomy_v2(
    kb_root: Path,
    *,
    prd_doc_id: str | None = None,
    pes_glob: str | None = None,
) -> TaxonomyConfigV2:
    """Auto-generate a hierarchical TaxonomyConfigV2 (system -> ... -> function).

    PRD provides system (H1) + subsystem (H2). When ``pes_glob`` is set,
    PES documents whose ``doc_id`` matches the glob are mounted under the
    PRD subsystem whose ``linked_specs`` includes the PES doc number:
    PES H1 entries become ``part`` nodes, PES H2 entries become
    ``function`` nodes.

    Same-name parts under different subsystems are kept separate.
    Deterministic: children are sorted by slug at every layer.
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
    if not index_path.is_file():
        raise FileNotFoundError(f"PRD index.json 不存在: {index_path}")
    root = json.loads(index_path.read_text(encoding="utf-8"))
    main_md = (prd_dir / "main.md").read_text(encoding="utf-8") \
        if (prd_dir / "main.md").is_file() else ""

    top_children = [c for c in root.get("children", []) if isinstance(c, dict)]

    # Build system -> subsystem skeleton from PRD H1/H2.
    # Map subsystem identity by (system_slug, subsystem_slug) for PES mounting.
    system_nodes: dict[str, dict] = {}
    subsystem_specs: dict[tuple[str, str], list[str]] = {}

    for h1 in top_children:
        title = str(h1.get("title", "")).strip()
        if not title:
            continue
        sys_slug = _slugify(title)
        if not sys_slug:
            continue

        sub_children = [c for c in h1.get("children", []) if isinstance(c, dict)]
        sub_anchor_pairs = _collect_anchor_pairs(sub_children)

        subsystems: dict[str, dict] = {}
        for (sub_node, (sub_anchor, sub_next)) in zip(
            sub_children, sub_anchor_pairs, strict=False
        ):
            sub_title = str(sub_node.get("title", "")).strip()
            if not sub_title:
                continue
            sub_slug = _slugify(sub_title)
            if not sub_slug or sub_slug in subsystems:
                continue
            sub_specs = _extract_subsystem_linked_specs(
                main_md, sub_anchor, sub_next,
            )
            subsystems[sub_slug] = {
                "slug": sub_slug, "title": sub_title, "layer": "subsystem",
                "prd_headings": (sub_title,),
                "linked_specs": tuple(sub_specs),
                "keywords": tuple(sorted(_tokenize(sub_title))),
                "parts": {},  # part_slug -> dict
            }
            subsystem_specs[(sys_slug, sub_slug)] = sub_specs

        # H1-level linked_specs (fall-through to subsystems is via PES anchor pairs)
        h1_anchor = str(h1.get("anchor", "")).strip()
        next_h1_anchor: str | None = None
        h1_index = top_children.index(h1)
        if h1_index + 1 < len(top_children):
            next_h1_anchor = str(top_children[h1_index + 1].get("anchor", "")).strip()
        h1_specs = _extract_subsystem_linked_specs(main_md, h1_anchor, next_h1_anchor)

        # If H1 has linked_specs but no subsystem captured them, hold for fallback mount.
        system_nodes[sys_slug] = {
            "slug": sys_slug, "title": title, "layer": "system",
            "prd_headings": (title,),
            "linked_specs": tuple(h1_specs),
            "keywords": tuple(sorted(_tokenize(title))),
            "subsystems": subsystems,
        }

    # Mount PES documents under matching subsystems
    if pes_glob:
        pes_docs = _discover_pes_docs(kb_root, pes_glob, prd_doc_id)
        for pes_doc in pes_docs:
            pes_index = json.loads(
                (kb_root / pes_doc / "index.json").read_text(encoding="utf-8"),
            )
            # Identify owning subsystem(s):
            #  (1) direct match: PES doc_id matches a subsystem's linked_specs
            #  (2) indirect match: PES doc_id matches a system's H1 linked_specs
            #      AND the PES doc name shares a token with the subsystem title
            #      (covers real PRDs whose Reference table sits at H1 level)
            owners: list[tuple[str, str]] = []
            for (sys_slug, sub_slug), specs in subsystem_specs.items():
                if any(_matches_linked_spec(pes_doc, pat) for pat in specs):
                    owners.append((sys_slug, sub_slug))
            if not owners:
                pes_tokens = _tokenize(pes_doc)
                for sys_slug, sys in system_nodes.items():
                    if not any(_matches_linked_spec(pes_doc, pat)
                               for pat in sys["linked_specs"]):
                        continue
                    for sub_slug, sub in sys["subsystems"].items():
                        sub_tokens = _tokenize(sub["title"])
                        if pes_tokens & sub_tokens:
                            owners.append((sys_slug, sub_slug))
            if not owners:
                continue
            pes_top = [c for c in pes_index.get("children", []) if isinstance(c, dict)]
            for h1 in pes_top:
                h1_title = str(h1.get("title", "")).strip()
                if not h1_title:
                    continue
                part_slug = _slugify(h1_title)
                if not part_slug:
                    continue
                h2_funcs: dict[str, dict] = {}
                for h2 in h1.get("children", []) or []:
                    if not isinstance(h2, dict):
                        continue
                    h2_title = str(h2.get("title", "")).strip()
                    if not h2_title:
                        continue
                    fn_slug = _slugify(h2_title)
                    if not fn_slug or fn_slug in h2_funcs:
                        continue
                    h2_funcs[fn_slug] = {
                        "slug": fn_slug, "title": h2_title, "layer": "function",
                        "pes_headings": (h2_title,),
                        "keywords": tuple(sorted(_tokenize(h2_title))),
                    }
                # Mount the same part separately under each owner subsystem
                for sys_slug, sub_slug in owners:
                    sub_dict = system_nodes[sys_slug]["subsystems"][sub_slug]
                    # Record the PES doc as an exact-match linked spec so
                    # build_pes_section_map_v2 can later find it.
                    existing = list(sub_dict["linked_specs"])
                    if pes_doc not in existing:
                        existing.append(pes_doc)
                        sub_dict["linked_specs"] = tuple(existing)
                    parts = sub_dict["parts"]
                    if part_slug not in parts:
                        parts[part_slug] = {
                            "slug": part_slug, "title": h1_title, "layer": "part",
                            "pes_headings": (h1_title,),
                            "keywords": tuple(sorted(_tokenize(h1_title))),
                            "functions": {},
                        }
                    # Merge function children (deterministic union by slug)
                    parts[part_slug]["functions"].update(h2_funcs)

    # Materialize into CategoryNode tree (sorted by slug at every layer)
    def _build_function(d: dict) -> CategoryNode:
        return CategoryNode(
            slug=d["slug"], title=d["title"], layer="function",
            pes_headings=d.get("pes_headings", ()),
            keywords=d.get("keywords", ()),
        )

    def _build_part(d: dict) -> CategoryNode:
        fns = tuple(_build_function(d["functions"][k])
                    for k in sorted(d["functions"]))
        return CategoryNode(
            slug=d["slug"], title=d["title"], layer="part",
            pes_headings=d.get("pes_headings", ()),
            keywords=d.get("keywords", ()),
            children=fns,
        )

    def _build_subsystem(d: dict) -> CategoryNode:
        parts = tuple(_build_part(d["parts"][k]) for k in sorted(d["parts"]))
        return CategoryNode(
            slug=d["slug"], title=d["title"], layer="subsystem",
            prd_headings=d.get("prd_headings", ()),
            linked_specs=d.get("linked_specs", ()),
            keywords=d.get("keywords", ()),
            children=parts,
        )

    def _build_system(d: dict) -> CategoryNode:
        subs = tuple(_build_subsystem(d["subsystems"][k])
                     for k in sorted(d["subsystems"]))
        return CategoryNode(
            slug=d["slug"], title=d["title"], layer="system",
            prd_headings=d.get("prd_headings", ()),
            linked_specs=d.get("linked_specs", ()),
            keywords=d.get("keywords", ()),
            children=subs,
        )

    categories = tuple(_build_system(system_nodes[k]) for k in sorted(system_nodes))
    cfg = TaxonomyConfigV2(
        version=2, source_prd=prd_doc_id,
        source_pes_glob=pes_glob, categories=categories,
    )
    validate_taxonomy_v2(cfg)
    return cfg


# --- Routing v2 ---


def _find_path_to_subsystem_by_linked_spec(
    cfg: TaxonomyConfigV2, doc_id: str,
) -> tuple[str, ...]:
    """Return (system, subsystem) path whose subsystem linked_specs matches."""
    for sys_node in cfg.categories:
        for sub in sys_node.children:
            for pat in sub.linked_specs:
                if _matches_linked_spec(doc_id, pat):
                    return (sys_node.slug, sub.slug)
        # Fallback: system-level linked_spec match
        for pat in sys_node.linked_specs:
            if _matches_linked_spec(doc_id, pat):
                return (sys_node.slug,)
    return ()


def _keyword_match_top_level(
    cfg: TaxonomyConfigV2, section_title: str,
) -> tuple[str, ...]:
    tokens = _tokenize(section_title)
    if not tokens:
        return ()
    best_slug = ""
    best_count = 0
    for sys_node in cfg.categories:
        # Aggregate keywords across the whole subtree of this system
        kws = set(_keyword_tokens(sys_node.keywords))
        for sub in sys_node.children:
            kws |= _keyword_tokens(sub.keywords)
            for part in sub.children:
                kws |= _keyword_tokens(part.keywords)
                for fn in part.children:
                    kws |= _keyword_tokens(fn.keywords)
        overlap = len(tokens & kws)
        if overlap > best_count:
            best_count = overlap
            best_slug = sys_node.slug
    return (best_slug,) if best_count > 0 else ()


def route_evidence_v2(
    ev: EvidenceRef,
    config: TaxonomyConfigV2,
    prd_section_map: dict[str, tuple[str, ...]],
    pes_section_map: dict[tuple[str, str], tuple[str, ...]],
) -> tuple[str, ...]:
    """Route an evidence ref to a category path (longest-prefix match).

    Priority (descending):
      1. PRD anchor map (when doc_id matches config.source_prd)
      2. PES anchor map (when (doc_id, anchor) appears)
      3. Subsystem ``linked_specs`` pattern matches ``doc_id``
      4. Keyword overlap with section_title (resolves to top-level system)
      5. Fallback to ``('_uncategorized',)``
    """
    # 1. PRD anchor map
    if _normalize_doc_id(ev.doc_id) == _normalize_doc_id(config.source_prd):
        path = prd_section_map.get(ev.anchor)
        if path:
            return tuple(path)
    else:
        # 2. PES anchor map (deepest specific match)
        path = pes_section_map.get((ev.doc_id, ev.anchor))
        if path:
            return tuple(path)
        # 3. Linked specs
        path = _find_path_to_subsystem_by_linked_spec(config, ev.doc_id)
        if path:
            return path

    # 4. Keyword fallback (top-level system)
    path = _keyword_match_top_level(config, ev.section_title)
    if path:
        return path

    return ("_uncategorized",)


def build_prd_section_map_v2(
    kb_root: Path,
    config: TaxonomyConfigV2,
) -> dict[str, tuple[str, ...]]:
    """Build PRD anchor -> (system_slug, [subsystem_slug]) map.

    Walks the PRD ``index.json`` and matches each H1 / H2 heading to a
    system / subsystem in the taxonomy by title equality.
    """
    kb_root = Path(kb_root)
    prd_dir = _resolve_child_casefold(kb_root, config.source_prd)
    if prd_dir is None:
        return {}
    prd_index = prd_dir / "index.json"
    if not prd_index.is_file():
        return {}
    root = json.loads(prd_index.read_text(encoding="utf-8"))
    result: dict[str, tuple[str, ...]] = {}

    def _match_h1_to_system(title: str) -> CategoryNode | None:
        tl = title.lower()
        for sys_node in config.categories:
            for ph in sys_node.prd_headings:
                if ph.lower() in tl:
                    return sys_node
        return None

    def _match_h2_to_subsystem(
        title: str, sys_node: CategoryNode,
    ) -> CategoryNode | None:
        tl = title.lower()
        for sub in sys_node.children:
            for ph in sub.prd_headings:
                if ph.lower() in tl:
                    return sub
        return None

    def _walk_descendants(node: dict, path: tuple[str, ...]) -> None:
        anchor = str(node.get("anchor", "")).strip()
        if anchor:
            result[anchor] = path
        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                _walk_descendants(child, path)

    for h1 in root.get("children", []) or []:
        if not isinstance(h1, dict):
            continue
        sys_node = _match_h1_to_system(str(h1.get("title", "")))
        if sys_node is None:
            continue
        h1_anchor = str(h1.get("anchor", "")).strip()
        if h1_anchor:
            result[h1_anchor] = (sys_node.slug,)
        # H2 children -> subsystem path; H3+ inherit deepest matched path
        for h2 in h1.get("children", []) or []:
            if not isinstance(h2, dict):
                continue
            sub = _match_h2_to_subsystem(str(h2.get("title", "")), sys_node)
            path: tuple[str, ...] = (
                (sys_node.slug, sub.slug) if sub is not None else (sys_node.slug,)
            )
            _walk_descendants(h2, path)
    return result


def build_pes_section_map_v2(
    kb_root: Path,
    config: TaxonomyConfigV2,
) -> dict[tuple[str, str], tuple[str, ...]]:
    """Build (doc_id, anchor) -> path map for all PES documents in the taxonomy.

    For each subsystem with non-empty ``linked_specs``, scan matching PES
    docs in ``kb_root`` and map their H1 anchors -> part path, H2 anchors
    -> function path.
    """
    kb_root = Path(kb_root)
    result: dict[tuple[str, str], tuple[str, ...]] = {}

    # Pre-collect subsystem -> (path, linked_specs, parts_by_slug, fns_by_part_slug)
    for sys_node in config.categories:
        for sub in sys_node.children:
            if not sub.linked_specs:
                continue
            parts_by_slug = {p.slug: p for p in sub.children}
            for d in sorted(kb_root.iterdir()):
                if not d.is_dir() or d.name == config.source_prd:
                    continue
                if not any(_matches_linked_spec(d.name, pat)
                           for pat in sub.linked_specs):
                    continue
                pes_index = d / "index.json"
                if not pes_index.is_file():
                    continue
                root = json.loads(pes_index.read_text(encoding="utf-8"))
                for h1 in root.get("children", []) or []:
                    if not isinstance(h1, dict):
                        continue
                    h1_title = str(h1.get("title", "")).strip()
                    if not h1_title:
                        continue
                    part_slug = _slugify(h1_title)
                    if part_slug not in parts_by_slug:
                        continue
                    part_path = (sys_node.slug, sub.slug, part_slug)
                    h1_anchor = str(h1.get("anchor", "")).strip()
                    if h1_anchor:
                        result[(d.name, h1_anchor)] = part_path
                    fns_by_slug = {f.slug for f in parts_by_slug[part_slug].children}
                    for h2 in h1.get("children", []) or []:
                        if not isinstance(h2, dict):
                            continue
                        h2_title = str(h2.get("title", "")).strip()
                        if not h2_title:
                            continue
                        fn_slug = _slugify(h2_title)
                        if fn_slug not in fns_by_slug:
                            # Anchor still rolls up to part level
                            anchor = str(h2.get("anchor", "")).strip()
                            if anchor:
                                result[(d.name, anchor)] = part_path
                            continue
                        anchor = str(h2.get("anchor", "")).strip()
                        if anchor:
                            result[(d.name, anchor)] = (*part_path, fn_slug)
    return result
