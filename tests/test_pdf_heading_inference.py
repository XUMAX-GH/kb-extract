"""SP-2 / v0.2.0: font-size heading inference for PDFs without a TOC."""

from __future__ import annotations

import fitz  # pymupdf
import pytest

from kb_extract.adapters.pdf_docling import PdfDoclingAdapter
from kb_extract.adapters.pdf_heading_infer import infer_headings


def _add_text(page, text, point, size, bold=False):
    """Insert text on a page at given point with given size and weight."""
    fontname = "helv-b" if bold else "helv"
    page.insert_text(point, text, fontsize=size, fontname=fontname)


def _make_pdf_with_font_headings(path):
    """Build a PDF with no TOC but clear font-size hierarchy.

    Page 1: huge title + body text
    Page 2: medium subtitle + body text
    Page 3: another huge title
    """
    doc = fitz.open()
    p1 = doc.new_page()
    _add_text(p1, "Chapter One Big Title", (72, 100), size=24)
    _add_text(p1, "This is regular body content on page one. " * 3,
              (72, 160), size=10)
    p2 = doc.new_page()
    _add_text(p2, "A Smaller Subtitle", (72, 100), size=16)
    _add_text(p2, "More body text continues here. " * 4, (72, 160), size=10)
    p3 = doc.new_page()
    _add_text(p3, "Chapter Two Big Title", (72, 100), size=24)
    _add_text(p3, "Final body content. " * 3, (72, 160), size=10)
    doc.save(str(path))
    doc.close()


@pytest.mark.disable_socket
def test_infer_headings_detects_two_levels_from_font_sizes(tmp_path):
    src = tmp_path / "doc.pdf"
    _make_pdf_with_font_headings(src)

    doc = fitz.open(str(src))
    result = infer_headings(doc)
    doc.close()

    assert result is not None
    assert len(result.headings) >= 2
    # Largest font (24pt) should map to level 1, medium (16pt) to level 2.
    levels_seen = {h.level for h in result.headings}
    assert 1 in levels_seen
    assert 2 in levels_seen
    # Largest size >= 2x body (10) → confidence medium
    assert result.confidence == "medium"


@pytest.mark.disable_socket
def test_pdf_adapter_uses_heading_inference_when_no_toc(tmp_path):
    src = tmp_path / "doc.pdf"
    _make_pdf_with_font_headings(src)

    out = tmp_path / "out.tmp"
    out.mkdir()
    result = PdfDoclingAdapter().extract(src, out)

    assert result.meta.outline_source == "heading_inferred"
    assert result.meta.outline_confidence in {"medium", "low"}
    # Should have at least the two big titles as level-1 nodes
    titles = [c.title for c in result.index.children]
    assert any("Chapter One" in t for t in titles)
    assert any("Chapter Two" in t for t in titles)


@pytest.mark.disable_socket
def test_pdf_adapter_falls_back_to_page_when_no_text(tmp_path):
    """A PDF with no extractable text → page_fallback, confidence low."""
    src = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(str(src))
    doc.close()

    out = tmp_path / "out.tmp"
    out.mkdir()
    result = PdfDoclingAdapter().extract(src, out)

    assert result.meta.outline_source == "page_fallback"
    assert result.meta.outline_confidence == "low"
    assert len(result.index.children) == 2


@pytest.mark.disable_socket
def test_heading_inference_is_deterministic(tmp_path):
    """Same PDF bytes → same inference result."""
    src = tmp_path / "doc.pdf"
    _make_pdf_with_font_headings(src)
    doc1 = fitz.open(str(src))
    r1 = infer_headings(doc1)
    doc1.close()
    doc2 = fitz.open(str(src))
    r2 = infer_headings(doc2)
    doc2.close()
    assert r1 == r2
