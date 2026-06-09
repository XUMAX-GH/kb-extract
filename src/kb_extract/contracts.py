"""Core data contract shared by adapters, orchestrator, hardness, and downstream layers.

All types here are `frozen=True, slots=True`. Changes to these types are
considered breaking and require a major version bump.

See spec §4 for rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class SectionNode:
    """PageIndex-style recursive section node.

    Each leaf corresponds to a contiguous span of main.md and carries an
    `anchor` that exists exactly once in main.md as `<a id="...">`.
    Non-leaf nodes have anchor == "" and aggregate their children.
    """

    node_id: str
    title: str
    level: int
    page_start: int
    page_end: int
    anchor: str
    language: str
    children: tuple[SectionNode, ...] = ()


@dataclass(frozen=True, slots=True)
class TableRef:
    """A table extracted with raw structured data, not just markdown rendering."""

    anchor: str
    page: int
    rows_json: tuple[tuple[str, ...], ...]
    rendered_asset: str | None


@dataclass(frozen=True, slots=True)
class AssetRef:
    """Image, rendered-table image, or embedded file."""

    kind: Literal["image", "table_image", "embedded_file"]
    rel_path: str
    page: int
    sha256: str
    width: int | None = None
    height: int | None = None
    alt: str = ""


@dataclass(frozen=True, slots=True)
class ExtractionMeta:
    source_path: str
    source_sha256: str
    source_bytes: int
    source_mtime_iso: str
    adapter_name: str
    adapter_version: str
    tool_versions: dict[str, str]
    extracted_at_iso: str
    outline_source: Literal["bookmark", "heading_style", "docling_layout", "page_fallback"]
    status: Literal["ok", "partial", "failed"]
    warnings: tuple[str, ...] = ()
    skipped_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    markdown: str
    index: SectionNode
    tables: tuple[TableRef, ...]
    assets: tuple[AssetRef, ...]
    meta: ExtractionMeta

    def content_sha256(self) -> str:
        """sha256 over (markdown bytes || sorted asset sha256s || index canonical bytes).

        Used for idempotency and verification. Asset order in the tuple does
        not affect the hash; assets are sorted by sha256 first. Markdown is
        normalized via ``serialize_markdown`` first so the hash matches the
        bytes actually written to disk (and re-read by ``kb verify``).
        """
        import hashlib

        from .serialization import canonical_index_bytes, serialize_markdown

        h = hashlib.sha256()
        h.update(serialize_markdown(self.markdown).encode("utf-8"))
        h.update(b"\x00ASSETS\x00")
        for a in sorted(self.assets, key=lambda a: a.sha256):
            h.update(a.sha256.encode("ascii"))
            h.update(b"\x00")
        h.update(b"\x00INDEX\x00")
        h.update(canonical_index_bytes(self.index))
        return h.hexdigest()
