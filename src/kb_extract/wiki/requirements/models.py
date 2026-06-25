"""TestItem model + tolerant LLM-JSON parsing/coercion."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

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


def coerce_item(obj: dict, *, anchor: str, section_title: str) -> TestItem:
    """Build a TestItem, forcing EvidenceRef/SourceSection from real context."""

    def s(key: str, default: str = "") -> str:
        val = obj.get(key, default)
        return str(val).strip() if val is not None else default

    return TestItem(
        category=s("Category") or "Uncategorized",
        function=s("Function"),
        what=s("What"),
        how=s("How") or DEFAULT_HOW,
        sample_size=s("Sample Size") or DEFAULT_SAMPLE,
        source_document=s("SourceDocument") or DEFAULT_DOC,
        source_section=section_title or s("SourceSection"),
        evidence_ref=anchor,  # ALWAYS the real anchor; never trust LLM
    )
