"""Tests for adapters._table_utils (v0.8.0 parser v2).

Pure-Python, deterministic: takes a 2D grid of CellInfo and emits HTML
<table> with rowspan/colspan attributes. No external deps.
"""
from __future__ import annotations

import pytest

from kb_extract.adapters._table_utils import CellInfo, cells_to_html

pytestmark = pytest.mark.disable_socket


def test_empty_table_returns_empty_table_tag() -> None:
    assert cells_to_html([]) == "<table></table>"


def test_single_cell() -> None:
    html = cells_to_html([[CellInfo(text="hello")]])
    assert html == "<table><tr><td>hello</td></tr></table>"


def test_plain_grid_2x2() -> None:
    rows = [
        [CellInfo("a"), CellInfo("b")],
        [CellInfo("c"), CellInfo("d")],
    ]
    html = cells_to_html(rows)
    assert html == (
        "<table>"
        "<tr><td>a</td><td>b</td></tr>"
        "<tr><td>c</td><td>d</td></tr>"
        "</table>"
    )


def test_header_row_emits_th() -> None:
    rows = [
        [CellInfo("h1", is_header=True), CellInfo("h2", is_header=True)],
        [CellInfo("a"), CellInfo("b")],
    ]
    html = cells_to_html(rows)
    assert "<th>h1</th><th>h2</th>" in html
    assert "<td>a</td><td>b</td>" in html


def test_colspan_only() -> None:
    rows = [
        [CellInfo("merged", colspan=2)],
        [CellInfo("c"), CellInfo("d")],
    ]
    html = cells_to_html(rows)
    assert '<td colspan="2">merged</td>' in html
    assert "<td>c</td><td>d</td>" in html


def test_rowspan_only() -> None:
    rows = [
        [CellInfo("tall", rowspan=2), CellInfo("b")],
        [CellInfo("d")],
    ]
    html = cells_to_html(rows)
    assert '<td rowspan="2">tall</td>' in html
    # Second row should NOT re-emit the spanned cell
    assert html.count("<td>tall</td>") == 0


def test_mixed_rowspan_and_colspan() -> None:
    rows = [
        [CellInfo("big", rowspan=2, colspan=2), CellInfo("x")],
        [CellInfo("y")],
    ]
    html = cells_to_html(rows)
    assert '<td colspan="2" rowspan="2">big</td>' in html


def test_empty_cell_becomes_nbsp() -> None:
    rows = [[CellInfo(""), CellInfo("b")]]
    html = cells_to_html(rows)
    assert "<td>&nbsp;</td>" in html
    assert "<td>b</td>" in html


def test_html_special_chars_escaped() -> None:
    rows = [[CellInfo("a & <b> \"c\"")]]
    html = cells_to_html(rows)
    assert "<td>a &amp; &lt;b&gt; &quot;c&quot;</td>" in html


def test_text_with_newlines_becomes_br() -> None:
    rows = [[CellInfo("line1\nline2")]]
    html = cells_to_html(rows)
    assert "line1<br>line2" in html


def test_rowspan_extends_beyond_table_clamped() -> None:
    """If rowspan exceeds rows below, cell still renders with declared span."""
    rows = [
        [CellInfo("tall", rowspan=5)],
        [CellInfo("b")],
    ]
    html = cells_to_html(rows)
    # We trust the caller's span declaration (matches python-docx behavior)
    assert 'rowspan="5"' in html


def test_deterministic_output() -> None:
    rows = [
        [CellInfo("h", is_header=True), CellInfo("v")],
        [CellInfo("a", rowspan=2), CellInfo("b")],
        [CellInfo("c")],
    ]
    out1 = cells_to_html(rows)
    out2 = cells_to_html(rows)
    assert out1 == out2
