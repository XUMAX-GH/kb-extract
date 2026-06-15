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
