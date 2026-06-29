"""Edge model + tolerant LLM-JSON parsing/coercion. Ids/relation enforced."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
RELATIONS = (
    "depends_on",
    "affects",
    "constrained_by",
    "validated_by",
    "implemented_by",
)
PENDING = "待验证"
_PENDING_CAP = 0.3


@dataclass(frozen=True, slots=True)
class Edge:
    source_id: str
    target_id: str
    relation: str
    evidence_ref: str
    confidence: float = 0.0
    flags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "evidence_ref": self.evidence_ref,
            "confidence": round(self.confidence, 2),
            "flags": sorted(self.flags),
        }

    def sort_key(self) -> tuple[str, str, str]:
        return (self.source_id, self.relation, self.target_id)


def parse_edges(raw: str) -> list[dict]:
    """Parse an LLM response into a list of dict edges (tolerant of fences/prose)."""
    text = _FENCE_RE.sub("", raw.strip()).strip()
    if not text.startswith("["):
        s, e = text.find("["), text.rfind("]")
        if s < 0 or e < 0 or e < s:
            raise ValueError("LLM response contains no JSON list")
        text = text[s : e + 1]
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("LLM response is not a JSON list")
    return [o for o in data if isinstance(o, dict)]


def coerce_edge(obj: dict, *, doc_id: str, valid_ids: set[str]) -> Edge | None:
    """Build an Edge, dropping hallucinated ids/relations and self-edges.

    Missing evidence flags the edge 待验证 and caps confidence. Never invents
    relations: an unknown relation drops the edge entirely.
    """

    def s(k: str) -> str:
        v = obj.get(k)
        return str(v).strip() if v is not None else ""

    src, tgt, rel = s("source_id"), s("target_id"), s("relation").lower()
    if rel not in RELATIONS:
        return None
    if src not in valid_ids or tgt not in valid_ids or src == tgt:
        return None
    try:
        conf = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    flags: list[str] = []
    evidence = s("evidence_ref")
    if not evidence:
        evidence = f"kb/{doc_id}/graph/atoms.json#{src}"
        flags.append(PENDING)
        conf = min(conf, _PENDING_CAP)
    return Edge(
        source_id=src,
        target_id=tgt,
        relation=rel,
        evidence_ref=evidence,
        confidence=conf,
        flags=tuple(dict.fromkeys(flags)),
    )
