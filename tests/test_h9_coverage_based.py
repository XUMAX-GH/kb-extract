"""TDD: regression tests for H9 false positives on real docs (v0.5.1).

Two real-data bugs from the BUR-K spec batch:

1. **DOCX multi-section on single page**: A docx is treated as page=1..1
   throughout; siblings at level >= 1 all claim page 1, which the old
   H9 (leaves-must-not-overlap) flagged as overlap. The coverage intent
   is satisfied — page 1 IS covered — so this should not violate.

2. **PDF interior-node intro content**: When the heading-inference
   produces a parent at page 1 with the first inferred child at page 2+,
   the parent (page 1..N) becomes an interior node and is excluded from
   the leaves-only walk. Page 1 is then "uncovered" by leaves and H9
   triggers a gap-before-first-leaf. The parent's intrinsic coverage
   (page 1 minus children's coverage = {1}) does cover the page; the
   check should account for it.

Fix: change H9 to **coverage-based** — union of every SectionNode's
``[page_start, page_end]`` (interior + leaf) must equal
``[1, total_pages]`` exactly. Per-node range validity (page_start <=
page_end, within bounds) is still enforced.
"""

from __future__ import annotations

import pytest

from kb_extract.contracts import SectionNode
from kb_extract.hardness import HardnessViolation, check_h9_page_range_closure


def _root_with(children: tuple[SectionNode, ...]) -> SectionNode:
    return SectionNode(
        node_id="0000", title="", level=0, page_start=1, page_end=1,
        anchor="", language="und", children=children,
    )


def test_h9_allows_multiple_leaves_on_single_page_docx() -> None:
    """3 sibling sections all on page 1 of a 1-page docx are valid."""
    children = tuple(
        SectionNode(
            node_id=f"{i:04d}", title=f"Section {i}", level=1,
            page_start=1, page_end=1, anchor=f"sec-{i:04d}", language="und",
        )
        for i in range(1, 4)
    )
    root = _root_with(children)
    # Should NOT raise.
    check_h9_page_range_closure(root, total_pages=1)


def test_h9_allows_interior_parent_with_intro_content_before_first_child() -> None:
    """Parent at page 1..10 with first child at page 3 — pages 1..2 are
    the parent's intro content, covered by the parent's node range."""
    child = SectionNode(
        node_id="0002", title="1.1", level=2,
        page_start=3, page_end=10, anchor="sec-0002", language="und",
    )
    parent = SectionNode(
        node_id="0001", title="Section 1", level=1,
        page_start=1, page_end=10, anchor="sec-0001", language="und",
        children=(child,),
    )
    root = _root_with((parent,))
    # Should NOT raise — parent + child together cover pages 1..10.
    check_h9_page_range_closure(root, total_pages=10)


def test_h9_still_catches_real_missing_pages() -> None:
    """Coverage-based check still rejects truly uncovered pages."""
    children = (
        SectionNode(
            node_id="0001", title="A", level=1,
            page_start=1, page_end=2, anchor="a", language="und",
        ),
        SectionNode(
            node_id="0002", title="B", level=1,
            page_start=5, page_end=10, anchor="b", language="und",
        ),
    )
    root = _root_with(children)
    with pytest.raises(HardnessViolation) as ei:
        check_h9_page_range_closure(root, total_pages=10)
    assert ei.value.invariant == "H9"
    assert "3" in ei.value.detail and "4" in ei.value.detail  # missing pages 3, 4


def test_h9_still_catches_invalid_page_range_per_node() -> None:
    """page_end < page_start is always invalid."""
    bad = SectionNode(
        node_id="0001", title="X", level=1,
        page_start=5, page_end=3, anchor="x", language="und",
    )
    root = _root_with((bad,))
    with pytest.raises(HardnessViolation) as ei:
        check_h9_page_range_closure(root, total_pages=5)
    assert ei.value.invariant == "H9"


def test_h9_still_catches_pages_outside_total_bounds() -> None:
    """A leaf claiming page > total_pages is invalid."""
    bad = SectionNode(
        node_id="0001", title="X", level=1,
        page_start=1, page_end=99, anchor="x", language="und",
    )
    root = _root_with((bad,))
    with pytest.raises(HardnessViolation) as ei:
        check_h9_page_range_closure(root, total_pages=5)
    assert ei.value.invariant == "H9"
