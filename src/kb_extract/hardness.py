"""Hardness invariants (spec §7).

All checkers are pure functions. Each raises `HardnessViolation` with
`invariant=<H#>` and a precise `detail` string. The orchestrator catches
nothing here — violations always reach the CLI.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from .contracts import SectionNode
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
