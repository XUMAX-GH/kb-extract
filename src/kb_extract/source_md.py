"""kb source layer (SP-2): markitdown -> image-free, redacted source.md.

markitdown is imported ONLY in this module (never under adapters/), so the
adapter-only LLM-import scan is unaffected. Conversion of local files needs
no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .redaction import RedactionPolicy, redact_text
from .serialization import serialize_markdown

_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HTML_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


def strip_images(markdown: str) -> tuple[str, int]:
    """Remove all markdown and HTML image references; return (text, count)."""
    text, n1 = _MD_IMAGE_RE.subn("", markdown)
    text, n2 = _HTML_IMG_RE.subn("", text)
    return text, n1 + n2


@dataclass(frozen=True, slots=True)
class SourceStats:
    images_stripped: int
    pn_redacted: int


def _markitdown_convert(src: Path) -> str:
    """Seam around markitdown; monkeypatched in tests. Local-only, no network."""
    from markitdown import MarkItDown

    return MarkItDown(enable_plugins=False).convert_local(str(src)).text_content


def convert_one(
    src: Path, policy: RedactionPolicy | None
) -> tuple[str, SourceStats]:
    """Convert one local file to a normalized, image-free, redacted source.md."""
    raw = _markitdown_convert(src)
    text, images = strip_images(raw)
    pn = 0
    if policy is not None and policy.enabled:
        text, pn = redact_text(text, policy)
    text = serialize_markdown(text)
    return text, SourceStats(images_stripped=images, pn_redacted=pn)
