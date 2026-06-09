"""Hardness invariants (spec §7).

All checkers are pure functions. Each raises `HardnessViolation` with
`invariant=<H#>` and a precise `detail` string. The orchestrator catches
nothing here — violations always reach the CLI.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from .contracts import AssetRef, ExtractionMeta, SectionNode
from .errors import HardnessViolation

_ANCHOR_RE = re.compile(r'<a id="([^"]+)"></a>')


def _iter_anchors(markdown: str) -> Iterable[str]:
    yield from _ANCHOR_RE.findall(markdown)


def _walk_leaves(node: SectionNode) -> Iterable[SectionNode]:
    if not node.children:
        yield node
        return
    for c in node.children:
        yield from _walk_leaves(c)


def check_h3_anchor_uniqueness(markdown: str) -> None:
    counts = Counter(_iter_anchors(markdown))
    dups = sorted(a for a, n in counts.items() if n > 1)
    if dups:
        raise HardnessViolation(
            invariant="H3",
            detail=f"duplicate anchor(s) in markdown: {dups[:5]}",
        )


def check_h4_anchor_completeness(markdown: str, index: SectionNode) -> None:
    md_anchors = set(_iter_anchors(markdown))
    missing = sorted(
        leaf.anchor for leaf in _walk_leaves(index)
        if leaf.anchor and leaf.anchor not in md_anchors
    )
    if missing:
        raise HardnessViolation(
            invariant="H4",
            detail=f"section-tree leaf anchors missing from markdown: {missing[:5]}",
        )


_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\((assets/[^)\s]+)")


def _md_referenced_assets(markdown: str) -> set[str]:
    return set(_MD_IMG_RE.findall(markdown))


def check_h5_asset_closure(
    markdown: str, assets: tuple[AssetRef, ...], out_dir: Path
) -> None:
    md_refs = _md_referenced_assets(markdown)
    assetref_paths = {a.rel_path for a in assets}

    assets_dir = out_dir / "assets"
    fs_files: set[str] = set()
    if assets_dir.exists():
        for p in sorted(assets_dir.rglob("*")):
            if p.is_file():
                fs_files.add(p.relative_to(out_dir).as_posix())

    # 1. Every markdown ref must be in AssetRefs.
    md_missing_in_refs = sorted(md_refs - assetref_paths)
    if md_missing_in_refs:
        raise HardnessViolation(
            invariant="H5",
            detail=f"markdown references not in AssetRefs: {md_missing_in_refs[:5]}",
        )
    # 2. Every markdown ref must exist on disk.
    md_missing_on_disk = sorted(md_refs - fs_files)
    if md_missing_on_disk:
        raise HardnessViolation(
            invariant="H5",
            detail=f"markdown references missing on disk: {md_missing_on_disk[:5]}",
        )
    # 3. No orphan files in assets/.
    orphans = sorted(fs_files - md_refs - assetref_paths)
    if orphans:
        raise HardnessViolation(
            invariant="H5",
            detail=f"orphan files in assets/: {orphans[:5]}",
        )


def check_h6_asset_hash_truth(
    assets: tuple[AssetRef, ...], out_dir: Path
) -> None:
    for a in assets:
        path = out_dir / a.rel_path
        if not path.exists():
            raise HardnessViolation(
                invariant="H6",
                detail=f"AssetRef points to missing file: {a.rel_path}",
            )
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != a.sha256:
            raise HardnessViolation(
                invariant="H6",
                detail=f"asset hash mismatch for {a.rel_path}: expected {a.sha256}, got {actual}",
            )


def check_h7_source_hash_truth(meta: ExtractionMeta, src_path: Path) -> None:
    actual = hashlib.sha256(src_path.read_bytes()).hexdigest()
    if actual != meta.source_sha256:
        raise HardnessViolation(
            invariant="H7",
            detail=(
                f"meta.source_sha256 lies about {meta.source_path}: "
                f"meta={meta.source_sha256}, actual={actual}"
            ),
        )


def _count_titled_descendants(node: SectionNode) -> int:
    """Count non-root nodes (level >= 1) with a non-empty title."""
    n = 0
    for c in node.children:
        if c.level >= 1 and c.title.strip():
            n += 1
        n += _count_titled_descendants(c)
    return n


def check_h9_page_range_closure(index: SectionNode, total_pages: int) -> None:
    """Union of leaf [page_start, page_end] must equal [1, total_pages] exactly."""
    leaves = sorted(_walk_leaves(index), key=lambda n: (n.page_start, n.page_end))
    if not leaves:
        raise HardnessViolation(
            invariant="H9",
            detail=f"no leaf sections found; cannot cover {total_pages} pages",
        )
    # Check overlap
    prev_end = 0
    for leaf in leaves:
        if leaf.page_start <= prev_end:
            raise HardnessViolation(
                invariant="H9",
                detail=(
                    f"page-range overlap at leaf {leaf.node_id}: "
                    f"starts at {leaf.page_start}, previous leaf ended at {prev_end}"
                ),
            )
        if leaf.page_start > prev_end + 1:
            raise HardnessViolation(
                invariant="H9",
                detail=(
                    f"page-range gap before leaf {leaf.node_id}: "
                    f"pages {prev_end + 1}..{leaf.page_start - 1} missing"
                ),
            )
        prev_end = leaf.page_end
    # Check end-of-doc coverage
    if prev_end != total_pages:
        raise HardnessViolation(
            invariant="H9",
            detail=(
                f"page-range does not reach end of doc: covered through {prev_end}, "
                f"total_pages={total_pages}"
            ),
        )


def check_h10_outline_source_truth(meta: ExtractionMeta, index: SectionNode) -> None:
    # `page_fallback` does not promise structure beyond per-page nodes.
    if meta.outline_source == "page_fallback":
        return
    # For `bookmark`, `heading_style`, `docling_layout`: at least one
    # non-root titled node must exist (otherwise the adapter is lying about
    # having found structure).
    if _count_titled_descendants(index) == 0:
        raise HardnessViolation(
            invariant="H10",
            detail=(
                f"outline_source={meta.outline_source!r} claims structured outline, "
                "but section tree has no non-root titled nodes"
            ),
        )
