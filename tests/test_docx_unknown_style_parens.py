"""TDD: docx.unknown_style warning regex must accept parenthesized
style names like "Normal (Web)", "Heading 1 (Char)", etc.

Real-world MS Word style names frequently include parentheses for
"linked" variants. The old regex ``[\\w\\- ]+`` rejected them, so any
DOCX using such a style failed H11.
"""

from __future__ import annotations

import pytest

from kb_extract.warnings_registry import is_warning_allowed


@pytest.mark.parametrize(
    "warning",
    [
        "docx.unknown_style:Normal (Web)",
        "docx.unknown_style:Heading 1 (Char)",
        "docx.unknown_style:Body Text 2",
        "docx.unknown_style:TOC 1",
        "docx.unknown_style:List Paragraph",
        "docx.unknown_style:DefaultParagraphFont",
    ],
)
def test_docx_unknown_style_accepts_realistic_word_style_names(warning: str) -> None:
    assert is_warning_allowed(warning), f"should be allowed: {warning!r}"


def test_docx_unknown_style_still_rejects_garbage() -> None:
    # Newlines and control characters should still be rejected.
    assert not is_warning_allowed("docx.unknown_style:Normal\nInjection")
    assert not is_warning_allowed("docx.unknown_style:")  # empty style name
