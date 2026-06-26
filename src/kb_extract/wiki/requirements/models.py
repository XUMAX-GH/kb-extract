"""TestItem model + tolerant LLM-JSON parsing/coercion."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def find_verbatim(quote: str, body: str) -> str | None:
    """Return the original span of ``body`` matching ``quote`` ignoring only
    whitespace differences, or ``None`` if there is no match.

    Both strings are whitespace-normalized (runs of whitespace -> single
    space, stripped) for comparison, but the returned value is the ORIGINAL
    text from ``body`` (so rendering preserves the source exactly). This is the
    zero-hallucination guard: an unverifiable quote yields ``None`` and is
    dropped by the caller -- never approximated.
    """
    q = _WS_RE.sub(" ", quote).strip()
    if not q:
        return None
    norm_chars: list[str] = []
    orig_index: list[int] = []
    prev_ws = False
    for i, ch in enumerate(body):
        if ch.isspace():
            if not prev_ws and norm_chars:
                norm_chars.append(" ")
                orig_index.append(i)
            prev_ws = True
        else:
            norm_chars.append(ch)
            orig_index.append(i)
            prev_ws = False
    norm = "".join(norm_chars)
    pos = norm.find(q)
    if pos < 0:
        return None
    start = orig_index[pos]
    end = orig_index[pos + len(q) - 1] + 1
    return body[start:end]

DEFAULT_HOW = "Not explicitly defined"
DEFAULT_SAMPLE = "Not specified"
DEFAULT_DOC = "Not explicitly stated"


@dataclass(frozen=True, slots=True)
class TestItem:
    __test__ = False  # tell pytest this dataclass is not a test class
    category: str
    function: str
    what: str
    how: str
    sample_size: str
    source_document: str
    source_section: str
    evidence_ref: str
    evidence_quote: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "Category": self.category,
            "Function": self.function,
            "What": self.what,
            "How": self.how,
            "Sample Size": self.sample_size,
            "SourceDocument": self.source_document,
            "SourceSection": self.source_section,
            "EvidenceRef": self.evidence_ref,
            "EvidenceQuote": self.evidence_quote,
        }

    def sort_key(self) -> tuple[str, str, str, str]:
        return (self.evidence_ref, self.category, self.function, self.what)


def parse_items(raw: str) -> list[dict]:
    """Parse an LLM response into a list of dict items.

    Tolerant: strips ```json fences and surrounding prose. Raises
    ValueError if the payload is not a JSON list of objects.
    """
    text = raw.strip()
    text = _FENCE_RE.sub("", text).strip()
    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]")
        if start < 0 or end < 0 or end < start:
            raise ValueError("LLM response contains no JSON list")
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("LLM response is not a JSON list")
    return [obj for obj in data if isinstance(obj, dict)]


def coerce_item(
    obj: dict, *, anchor: str, section_title: str, category: str | None = None,
    section_body: str = ""
) -> TestItem:
    """Build a TestItem, forcing EvidenceRef/SourceSection from real context.

    When ``category`` is provided it is forced onto the item (the document's
    own chapter heading), overriding whatever the LLM emitted -- this keeps
    grouping deterministic and tied to the document structure.
    """

    def s(key: str, default: str = "") -> str:
        val = obj.get(key, default)
        return str(val).strip() if val is not None else default

    if category is not None:
        cat = category.strip() or "Uncategorized"
    else:
        cat = s("Category") or "Uncategorized"

    raw_quote = s("EvidenceQuote")
    verified = find_verbatim(raw_quote, section_body) if raw_quote else None

    return TestItem(
        category=cat,
        function=s("Function"),
        what=s("What"),
        how=s("How") or DEFAULT_HOW,
        sample_size=s("Sample Size") or DEFAULT_SAMPLE,
        source_document=s("SourceDocument") or DEFAULT_DOC,
        source_section=section_title or s("SourceSection"),
        evidence_ref=anchor,  # ALWAYS the real anchor; never trust LLM
        evidence_quote=verified or "",
    )
