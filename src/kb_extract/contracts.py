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
