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
from .warnings_registry import is_warning_allowed

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


def _walk_non_root(node: SectionNode) -> Iterable[SectionNode]:
    """Yield every node except the root (level 0 wrapper)."""
    for c in node.children:
        yield c
        yield from _walk_non_root(c)


def check_h9_page_range_closure(index: SectionNode, total_pages: int) -> None:
    """Every page in ``[1, total_pages]`` must be covered by at least one
    SectionNode (interior or leaf).

    v0.5.1 (coverage-based): the original "leaves-only, no-overlap"
    formulation falsely rejected two legitimate real-world shapes:

      * Single-page docs (DOCX/XLSX) where multiple sibling sections all
        live on page 1 — the union still covers page 1.
      * Hierarchical PDFs where a parent at page 1..N has its first child
        starting at page 3+ — pages 1..2 are the parent's intro content,
        covered by the parent's own range though not by any leaf.

    The check is now: union of every non-root SectionNode's
    ``[page_start, page_end]`` must equal ``{1, ..., total_pages}``
    exactly. Per-node validity (page_start <= page_end, both within
    bounds) is still enforced.
    """
    nodes = list(_walk_non_root(index))
    if not nodes:
        raise HardnessViolation(
            invariant="H9",
            detail=f"no sections found; cannot cover {total_pages} pages",
        )
    covered: set[int] = set()
    for n in nodes:
        if n.page_start < 1 or n.page_end < n.page_start:
            raise HardnessViolation(
                invariant="H9",
                detail=(
                    f"invalid page range on node {n.node_id}: "
                    f"page_start={n.page_start}, page_end={n.page_end}"
                ),
            )
        if n.page_end > total_pages:
            raise HardnessViolation(
                invariant="H9",
                detail=(
                    f"node {n.node_id} page_end={n.page_end} exceeds "
                    f"total_pages={total_pages}"
                ),
            )
        covered.update(range(n.page_start, n.page_end + 1))
    expected = set(range(1, total_pages + 1))
    missing = sorted(expected - covered)
    if missing:
        # Format compactly: show first 10 missing pages with ellipsis if more.
        shown = ", ".join(str(p) for p in missing[:10])
        more = f", ... ({len(missing)} pages total)" if len(missing) > 10 else ""
        raise HardnessViolation(
            invariant="H9",
            detail=f"pages not covered by any section: [{shown}]{more}",
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


def check_h11_warnings_allowlist(meta: ExtractionMeta) -> None:
    bad = sorted(w for w in meta.warnings if not is_warning_allowed(w))
    if bad:
        raise HardnessViolation(
            invariant="H11",
            detail=f"warnings not in allowlist: {bad[:5]}",
        )


def check_h22_image_integrity(markdown: str, out_dir: Path) -> None:
    """H22: every ``![](assets/...)`` reference must point at a file whose
    magic bytes identify it as a supported image format.

    Catches the case where ``save_image()`` was bypassed and a text file
    (or empty file) was written under the image extension. Complements
    H5 (existence/closure) and H6 (sha truth) with content validation.
    """
    from .adapters._image_utils import detect_image_format

    bad: list[str] = []
    for rel in sorted(_md_referenced_assets(markdown)):
        path = out_dir / rel
        try:
            blob = path.read_bytes()
        except OSError:
            bad.append(f"{rel} (unreadable)")
            continue
        if detect_image_format(blob) is None:
            bad.append(f"{rel} (no valid image magic bytes)")
    if bad:
        raise HardnessViolation(
            invariant="H22",
            detail=f"image-integrity failures: {bad[:5]}",
        )


def assert_invariants(
    result, src_path: Path, out_dir: Path, *, total_pages: int
) -> None:
    """Run H3..H7, H9..H11, H22 in order, raising on the first violation.

    H1 (no socket) and H2 (no LLM imports) are test-level checks.
    H8 (determinism) is a test-mode check (double-run compare).
    H12 (no silent skip) is enforced by the orchestrator.
    H13 (cross-platform) is enforced in CI.
    """
    check_h3_anchor_uniqueness(result.markdown)
    check_h4_anchor_completeness(result.markdown, result.index)
    check_h5_asset_closure(result.markdown, result.assets, out_dir)
    check_h6_asset_hash_truth(result.assets, out_dir)
    check_h7_source_hash_truth(result.meta, src_path)
    check_h9_page_range_closure(result.index, total_pages)
    check_h10_outline_source_truth(result.meta, result.index)
    check_h11_warnings_allowlist(result.meta)
    check_h22_image_integrity(result.markdown, out_dir)
