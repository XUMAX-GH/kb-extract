"""Deterministic YAML frontmatter for Obsidian-compatible wiki pages.

Hand-rolled emitter (no PyYAML dependency) with a fixed key order and sorted
list values so output is byte-identical across platforms (H13).
"""

from __future__ import annotations

# Fixed emission order. Keys absent from a given frontmatter dict are skipped.
_KEY_ORDER = (
    "title",
    "type",
    "domain",
    "category_path",
    "slug",
    "evidence_sources",
    "tags",
)

_NEEDS_QUOTE = set(':#[]{}",&*!|>%@`')


def build_frontmatter(
    *,
    title: str,
    category_path: tuple[str, ...],
    slug: str,
    doc_ids: list[str],
    page_type: str = "topic",
    extra_tags: list[str] | None = None,
) -> dict[str, object]:
    """Build a frontmatter dict from deterministic topic metadata."""
    domain = category_path[0] if category_path else "_uncategorized"
    tags = {f"domain/{domain}"}
    for seg in category_path:
        tags.add(f"path/{seg}")
    for t in extra_tags or []:
        tags.add(t)
    return {
        "title": title,
        "type": page_type,
        "domain": domain,
        "category_path": "/".join(category_path) if category_path else domain,
        "slug": slug,
        "evidence_sources": sorted(set(doc_ids)),
        "tags": sorted(tags),
    }


def _scalar(value: str) -> str:
    if value == "" or any(c in _NEEDS_QUOTE for c in value) or value != value.strip():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def render_frontmatter(fm: dict[str, object]) -> str:
    """Render a frontmatter dict to a deterministic ``---`` YAML block."""
    lines = ["---"]
    for key in _KEY_ORDER:
        if key not in fm:
            continue
        val = fm[key]
        if isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            else:
                rendered = ", ".join(_scalar(str(v)) for v in val)
                lines.append(f"{key}: [{rendered}]")
        else:
            lines.append(f"{key}: {_scalar(str(val))}")
    lines.append("---")
    return "\n".join(lines) + "\n"
