"""Read a single section's body text from a generated ``main.md``.

The wiki layer feeds these body excerpts to the LLM so that topic summaries
are based on real content, not just section titles.

A ``main.md`` produced by ``kb-extract`` looks like::

    <a id="sec-0001"></a>
    # Section title

    body markdown...

    <a id="sec-0002"></a>
    # Next section
    ...

Inline anchors such as ``<a id="tbl-0001"></a>`` for tables sit inside a
section body and must NOT terminate it. Only the next ``<a id="sec-NNNN"></a>``
boundary closes the current section.
"""

from __future__ import annotations

import re
from pathlib import Path

# Match exactly: <a id="<requested-anchor>"></a>
# We do NOT match generously (no \s* etc) because we need an exact anchor lookup.
_NEXT_SEC_RE = re.compile(r'<a id="sec-\d+"></a>')

# Default cap on body excerpt fed to LLM (chars). Roughly 500 tokens for English,
# ~1000 tokens for CJK at this size. Keeps prompts well under common LLM windows
# even with 10+ evidence sections.
_DEFAULT_MAX_CHARS = 1500


def read_section_body(
    kb_root: Path,
    doc_id: str,
    anchor: str,
    *,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str:
    """Return the markdown body of ``doc_id``'s ``anchor`` section.

    Returns an empty string if the document or anchor is missing. The opening
    ``<a id="..."></a>`` tag is stripped; the body starts at the line after.
    The body extends until the next ``<a id="sec-NNNN"></a>`` anchor or EOF,
    whichever comes first. If the body exceeds ``max_chars``, it is truncated
    and a single ``…`` (U+2026) is appended.
    """
    main_md = Path(kb_root) / doc_id / "main.md"
    if not main_md.is_file():
        return ""

    text = main_md.read_text(encoding="utf-8")
    needle = f'<a id="{anchor}"></a>'
    start = text.find(needle)
    if start < 0:
        return ""

    body_start = start + len(needle)
    # Skip a single trailing newline so the body starts on the next line.
    if body_start < len(text) and text[body_start] == "\n":
        body_start += 1

    # Find the next sec-NNNN anchor strictly after body_start.
    m = _NEXT_SEC_RE.search(text, body_start)
    body_end = m.start() if m else len(text)

    body = text[body_start:body_end].rstrip()

    if len(body) > max_chars:
        # Truncate; keep boundary clean (rstrip the cut, then append ellipsis).
        body = body[: max_chars - 1].rstrip() + "…"

    return body
