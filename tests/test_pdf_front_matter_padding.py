"""Regression for the Cpk-data bug: when first inferred heading or first TOC
entry is on page > 1, the prefix pages were left uncovered and H9 (page-range
gap closure) would fail extraction.

Reproduces a 2-page PDF whose page 1 has no text (image-only) and page 2 has a
large-font title + body text. Before the fix, font-size inference produced a
single heading on page 2; H9 caught "pages 1..1 missing".
"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from kb_extract.adapters.pdf_docling import PdfDoclingAdapter


def _build_2page_pdf_with_image_only_first(target: Path) -> None:
    doc = fitz.open()
    # Page 1: no text, just a filled rect (simulates an image-only scan).
    p1 = doc.new_page(width=612, height=792)
    p1.draw_rect(fitz.Rect(50, 50, 562, 742), color=(0, 0, 0), fill=(0.9, 0.9, 0.9))
    # Page 2: a large-font heading + body so font-size inference picks it.
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((72, 100), "Initial data (Before reflow soldering)",
                   fontname="helv", fontsize=22)
    p2.insert_text((72, 150), "Part Name: 4.9mm SMD Light Touch Switch",
                   fontname="helv", fontsize=10)
    p2.insert_text((72, 170), "Cpk = 1.67, n = 30 samples",
                   fontname="helv", fontsize=10)
    doc.save(str(target))
    doc.close()


@pytest.fixture
def cpk_like_pdf(tmp_path: Path) -> Path:
    out = tmp_path / "cpk_like.pdf"
    _build_2page_pdf_with_image_only_first(out)
    return out


def test_inferred_path_pads_front_matter_for_image_only_prefix(
    cpk_like_pdf: Path, tmp_path: Path,
) -> None:
    """The inferred path must synthesize a front-matter section covering page 1."""
    out_tmp = tmp_path / "out"
    out_tmp.mkdir()
    result = PdfDoclingAdapter().extract(cpk_like_pdf, out_tmp)

    # Collect every (page_start, page_end) across the tree's leaves.
    covered: set[int] = set()

    def _walk(node):
        if not node.children:
            for p in range(node.page_start, node.page_end + 1):
                covered.add(p)
        for c in node.children:
            _walk(c)

    for top in result.index.children:
        _walk(top)

    # Every page 1..n must be covered by some leaf.
    assert covered == {1, 2}, f"expected pages {{1,2}} covered, got {covered}"


def test_inferred_path_coalesces_multiple_headings_on_same_page(
    tmp_path: Path,
) -> None:
    """When font inference picks up multiple heading-sized spans on the same page,
    they must collapse to a single leaf so H9 (no overlapping page ranges) holds.

    Mirrors the EVPBKEA6B000 Cpk-data PDF case: page 1 is image-only, page 2
    has a mix of font sizes that all qualify as headings.
    """
    pdf = tmp_path / "multi_heading_on_p2.pdf"
    doc = fitz.open()
    p1 = doc.new_page(width=612, height=792)
    p1.draw_rect(fitz.Rect(50, 50, 562, 742), fill=(0.9, 0.9, 0.9))
    p2 = doc.new_page(width=612, height=792)
    # Three different heading-sized spans on the same page, plus body.
    p2.insert_text((72, 80), "Initial data", fontname="helv", fontsize=22)
    p2.insert_text((72, 130), "Part Name", fontname="helv", fontsize=16)
    p2.insert_text((72, 180), "Cpk Summary", fontname="helv", fontsize=14)
    p2.insert_text((72, 230), "body body body body " * 4, fontname="helv", fontsize=10)
    doc.save(str(pdf))
    doc.close()

    out_tmp = tmp_path / "out"
    out_tmp.mkdir()
    result = PdfDoclingAdapter().extract(pdf, out_tmp)

    # H9 requires disjoint, contiguous page ranges across leaves.
    leaves: list = []

    def _collect(node):
        if not node.children:
            leaves.append(node)
        for c in node.children:
            _collect(c)

    for top in result.index.children:
        _collect(top)

    # No two leaves may overlap on a page.
    leaves.sort(key=lambda n: (n.page_start, n.page_end))
    prev_end = 0
    for leaf in leaves:
        assert leaf.page_start > prev_end, (
            f"leaf {leaf.node_id} starts at {leaf.page_start}, prev_end={prev_end}"
        )
        prev_end = leaf.page_end
    assert prev_end == 2, f"leaves should cover up to page 2, got {prev_end}"


def test_toc_path_pads_front_matter_when_first_entry_after_page_1(
    tmp_path: Path,
) -> None:
    """When TOC's first entry is on page 2+, the prefix must still be covered."""
    pdf = tmp_path / "toc_after_p1.pdf"
    doc = fitz.open()
    # 3 pages, TOC entry only points at page 2.
    for _ in range(3):
        doc.new_page(width=612, height=792)
    doc[1].insert_text((72, 100), "Real chapter", fontname="helv", fontsize=14)
    doc.set_toc([[1, "Real chapter", 2]])
    doc.save(str(pdf))
    doc.close()

    out_tmp = tmp_path / "out"
    out_tmp.mkdir()
    result = PdfDoclingAdapter().extract(pdf, out_tmp)

    covered: set[int] = set()

    def _walk(node):
        if not node.children:
            for p in range(node.page_start, node.page_end + 1):
                covered.add(p)
        for c in node.children:
            _walk(c)

    for top in result.index.children:
        _walk(top)

    assert covered == {1, 2, 3}, f"expected pages {{1,2,3}} covered, got {covered}"
