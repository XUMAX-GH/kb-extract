"""SP-2 / v0.2.0: PDF adapter builds a recursive tree from a leveled TOC."""

from __future__ import annotations

import fitz  # pymupdf
import pytest

from kb_extract.adapters.pdf_docling import PdfDoclingAdapter


def _make_pdf_with_toc(path, toc):
    """Build a PDF with one blank page per TOC entry and set its outline."""
    doc = fitz.open()
    n_pages = max(t[2] for t in toc) if toc else 1
    for _ in range(n_pages):
        doc.new_page()
    if toc:
        doc.set_toc(toc)
    doc.save(str(path))
    doc.close()


@pytest.mark.disable_socket
def test_pdf_adapter_builds_recursive_tree_from_leveled_toc(tmp_path):
    """TOC with mixed levels yields a proper nested SectionNode tree."""
    src = tmp_path / "doc.pdf"
    # [level, title, start_page]
    toc = [
        [1, "Chapter 1", 1],
        [2, "Section 1.1", 1],
        [2, "Section 1.2", 2],
        [1, "Chapter 2", 3],
        [2, "Section 2.1", 3],
        [3, "Subsection 2.1.1", 3],
    ]
    _make_pdf_with_toc(src, toc)

    out = tmp_path / "out.tmp"
    out.mkdir()
    result = PdfDoclingAdapter().extract(src, out)

    assert result.meta.outline_source == "bookmark"
    assert result.meta.outline_confidence == "high"

    # Top-level children: Chapter 1 and Chapter 2
    chapters = result.index.children
    assert len(chapters) == 2
    assert chapters[0].title == "Chapter 1"
    assert chapters[1].title == "Chapter 2"
    assert chapters[0].level == 1
    assert chapters[1].level == 1

    # Chapter 1 has two children (Section 1.1, Section 1.2), both level=2
    ch1 = chapters[0]
    assert [c.title for c in ch1.children] == ["Section 1.1", "Section 1.2"]
    assert all(c.level == 2 for c in ch1.children)

    # Chapter 2 has one child Section 2.1, which has one grandchild Subsection 2.1.1
    ch2 = chapters[1]
    assert len(ch2.children) == 1
    sec21 = ch2.children[0]
    assert sec21.title == "Section 2.1"
    assert sec21.level == 2
    assert len(sec21.children) == 1
    assert sec21.children[0].title == "Subsection 2.1.1"
    assert sec21.children[0].level == 3


@pytest.mark.disable_socket
def test_pdf_adapter_page_ranges_respect_nesting(tmp_path):
    """The end_page of a parent extends to the last leaf, not just its own start."""
    src = tmp_path / "doc.pdf"
    toc = [
        [1, "Chapter 1", 1],
        [2, "Section 1.1", 2],
        [1, "Chapter 2", 5],
    ]
    _make_pdf_with_toc(src, toc)

    out = tmp_path / "out.tmp"
    out.mkdir()
    result = PdfDoclingAdapter().extract(src, out)

    chapters = result.index.children
    assert len(chapters) == 2
    ch1 = chapters[0]
    # Chapter 1 covers pages 1..4 (up to the page before Chapter 2)
    assert ch1.page_start == 1
    assert ch1.page_end == 4
