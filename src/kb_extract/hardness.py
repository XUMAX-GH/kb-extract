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

from .contracts import AssetRef, SectionNode
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
