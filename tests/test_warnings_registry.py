import re

import pytest

from kb_extract.warnings_registry import (
    ALLOWED_WARNING_PATTERNS,
    is_warning_allowed,
)


@pytest.mark.parametrize(
    "warning",
    [
        "pdf.scanned_no_text_layer",
        "pdf.password_protected",
        "pdf.low_confidence_heading:p12",
        "pdf.font_decode_failed:p3",
        "docx.unknown_style:Heading99",
        "docx.embedded_ole_skipped:oleObject1.bin",
        "xlsx.formula_empty_cache:Sheet1!A3",
        "xlsx.merged_cells_flattened:Sheet1!B2:C4",
        "pptx.animation_ignored:slide5",
        "image.exif:Make=Canon",
        "zip.encrypted:inner.docx",
        "zip.too_nested:depth=6",
    ],
)
def test_known_warnings_are_allowed(warning):
    assert is_warning_allowed(warning), f"{warning!r} not matched by any allowed pattern"


@pytest.mark.parametrize(
    "warning",
    [
        "freeform note from adapter",
        "WARNING: something happened",
        "pdf.totally_made_up_category",
        "image.exif",  # missing tag=value
        "",
    ],
)
def test_unknown_warnings_are_rejected(warning):
    assert not is_warning_allowed(warning)


def test_all_patterns_compile():
    for p in ALLOWED_WARNING_PATTERNS:
        re.compile(p)
