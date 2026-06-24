"""kb source layer (SP-2): markitdown -> image-free, redacted source.md.

markitdown is imported ONLY in this module (never under adapters/), so the
adapter-only LLM-import scan is unaffected. Conversion of local files needs
no network.
"""

from __future__ import annotations

import re

_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HTML_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


def strip_images(markdown: str) -> tuple[str, int]:
    """Remove all markdown and HTML image references; return (text, count)."""
    text, n1 = _MD_IMAGE_RE.subn("", markdown)
    text, n2 = _HTML_IMG_RE.subn("", text)
    return text, n1 + n2
