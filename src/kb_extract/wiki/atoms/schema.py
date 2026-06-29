"""Atom model + tolerant LLM-JSON parsing/coercion. Source/anchor/id forced."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_VALID_TYPES = ("requirement", "behavior", "constraint", "spec")
PENDING = "待验证"


def atom_id(
    *, entity: str, parameter: str, condition: str, source_doc: str, section: str
) -> str:
    key = "|".join(
        [
            entity.strip().lower(),
            parameter.strip().lower(),
            condition.strip().lower(),
            source_doc,
            section,
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class Atom:
    id: str
    entity: str
    parameter: str
    value: str | None
    unit: str
    type: str
    condition: str
    source_doc: str
    section: str
    evidence_ref: str
    confidence: float = 0.0
    flags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity": self.entity,
            "parameter": self.parameter,
            "value": self.value,
            "unit": self.unit,
            "type": self.type,
            "condition": self.condition,
            "source_doc": self.source_doc,
            "section": self.section,
            "evidence_ref": self.evidence_ref,
            "confidence": round(self.confidence, 2),
            "flags": sorted(self.flags),
        }

    def sort_key(self) -> tuple[str, str, str]:
        return (self.section, self.entity, self.id)


def parse_atoms(raw: str) -> list[dict]:
    """Parse an LLM response into a list of dict atoms (tolerant of fences/prose)."""
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


def coerce_atom(obj: dict, *, doc_id: str, anchor: str) -> Atom:
    """Build an Atom, forcing id/source_doc/section/evidence_ref from real context.

    Missing value or invalid type flags the atom 待验证 (never inferred). Key
    engineering parameters are never fabricated.
    """

    def s(k: str) -> str:
        v = obj.get(k)
        return str(v).strip() if v is not None else ""

    flags: list[str] = []
    entity, parameter, condition = s("entity"), s("parameter"), s("condition")
    raw_val = obj.get("value")
    value = str(raw_val).strip() if raw_val is not None and str(raw_val).strip() else None
    if value is None:
        flags.append(PENDING)
    atype = s("type").lower()
    if atype not in _VALID_TYPES:
        atype = "spec"
        flags.append(PENDING)
    try:
        conf = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return Atom(
        id=atom_id(
            entity=entity, parameter=parameter, condition=condition,
            source_doc=doc_id, section=anchor,
        ),
        entity=entity,
        parameter=parameter,
        value=value,
        unit=s("unit"),
        type=atype,
        condition=condition,
        source_doc=doc_id,
        section=anchor,
        evidence_ref=f"kb/{doc_id}/main.md#{anchor}",
        confidence=conf,
        flags=tuple(dict.fromkeys(flags)),
    )
