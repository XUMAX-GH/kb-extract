"""H11: warnings allowlist. Every warning emitted by an adapter must match
exactly one regex below. Add a new pattern here when introducing a new
warning category; do not emit freeform warnings.
"""

from __future__ import annotations

import re

ALLOWED_WARNING_PATTERNS: tuple[str, ...] = (
    # PDF / docling adapter
    r"^pdf\.scanned_no_text_layer$",
    r"^pdf\.scanned_page:p\d+$",
    r"^pdf\.password_protected$",
    r"^pdf\.low_confidence_heading:p\d+$",
    r"^pdf\.font_decode_failed:p\d+$",
    # DOCX adapter
    # Word style names can contain letters, digits, spaces, hyphens,
    # parens (e.g. "Normal (Web)"), commas, dots (e.g. "ListNumber.5").
    r"^docx\.unknown_style:[\w\- ().,]+$",
    r"^docx\.embedded_ole_skipped:[\w\-. ]+$",
    # XLSX adapter
    r"^xlsx\.formula_empty_cache:[^!]+![A-Z]+\d+$",
    r"^xlsx\.merged_cells_flattened:[^!]+![A-Z]+\d+:[A-Z]+\d+$",
    # PPTX adapter
    r"^pptx\.animation_ignored:slide\d+$",
    # Image adapter
    r"^image\.exif:[\w]+=[^\s]+$",
    # ZIP adapter
    r"^zip\.encrypted:[\w\-.]+$",
    r"^zip\.too_nested:depth=\d+$",
)

_compiled = tuple(re.compile(p) for p in ALLOWED_WARNING_PATTERNS)


def is_warning_allowed(warning: str) -> bool:
    """True iff `warning` matches at least one registered pattern."""
    return any(p.match(warning) for p in _compiled)
