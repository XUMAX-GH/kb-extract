"""Shared table rendering for v0.8.0 parser adapters.

Converts a 2D grid of ``CellInfo`` into an HTML ``<table>`` with
``rowspan``/``colspan`` attributes preserved. Markdown does not support
merged cells, so DOCX/PPTX/XLSX v2 adapters emit raw HTML tables that
pandoc and most markdown renderers accept as inline HTML.

Pure-Python, deterministic, no external deps. Caller is responsible for
producing a "phantom-free" grid: when a cell spans rows/columns, the
covered positions in subsequent rows MUST be omitted from the input
(matches the natural shape of python-docx / python-pptx / openpyxl
iteration after spans are coalesced).
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True, slots=True)
class CellInfo:
    """Single table cell with optional row/col span and header flag."""

    text: str
    rowspan: int = 1
    colspan: int = 1
    is_header: bool = False


def _render_cell_text(text: str) -> str:
    if not text:
        return "&nbsp;"
    escaped = escape(text, quote=True)
    return escaped.replace("\n", "<br>")


def _cell_attrs(cell: CellInfo) -> str:
    parts: list[str] = []
    if cell.colspan > 1:
        parts.append(f'colspan="{cell.colspan}"')
    if cell.rowspan > 1:
        parts.append(f'rowspan="{cell.rowspan}"')
    return (" " + " ".join(parts)) if parts else ""


def cells_to_html(rows: list[list[CellInfo]]) -> str:
    """Render a 2D grid of cells to an HTML ``<table>``.

    Empty input returns ``<table></table>``. Cell text is HTML-escaped;
    newlines become ``<br>``. Empty text becomes ``&nbsp;``.
    """
    if not rows:
        return "<table></table>"

    parts: list[str] = ["<table>"]
    for row in rows:
        parts.append("<tr>")
        for cell in row:
            tag = "th" if cell.is_header else "td"
            attrs = _cell_attrs(cell)
            parts.append(f"<{tag}{attrs}>{_render_cell_text(cell.text)}</{tag}>")
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)
