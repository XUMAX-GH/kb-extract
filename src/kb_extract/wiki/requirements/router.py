"""Deterministic section-to-domain router (ports CTx section-router rules).

No LLM. Same input -> same output. Section heading text is matched
case-insensitively against keyword lists; a leading section number
(e.g. "3.2.1") is matched against per-domain section_patterns.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

FALLBACK_DOMAIN = "base-extraction"

_RULES_PATH = Path(__file__).with_name("assets") / "domain_rules.json"
# Leading section number like "3", "3.2", "3.2.1" — trailing dot excluded from capture.
_SECTION_NO_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)")


@dataclass(frozen=True, slots=True)
class RouteResult:
    domain: str
    method: str  # "section_pattern" | "keyword" | "fallback"


@lru_cache(maxsize=1)
def _load_rules() -> dict[str, dict[str, list[str]]]:
    raw = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    # Normalise: keep insertion order deterministic via sorted domain names.
    return {k: raw[k] for k in sorted(raw)}


def _section_number(title: str) -> str:
    m = _SECTION_NO_RE.match(title)
    return m.group(1) if m else ""


def route_heading(title: str) -> RouteResult:
    """Route a single section heading to a domain.

    Priority:
      1. section_patterns match (deterministic by sorted domain name)
      2. highest keyword hit count
      3. fallback to base-extraction
    """
    rules = _load_rules()
    sec_no = _section_number(title)
    lower = title.lower()

    if sec_no:
        candidates = (sec_no, sec_no + ".")
        for domain in sorted(rules):
            for pat in rules[domain].get("section_patterns", []):
                if any(re.search(pat, c) for c in candidates):
                    return RouteResult(domain=domain, method="section_pattern")

    best_domain = ""
    best_hits = 0
    for domain in sorted(rules):
        hits = sum(1 for kw in rules[domain].get("keywords", []) if kw.lower() in lower)
        if hits > best_hits:
            best_hits = hits
            best_domain = domain

    if best_hits > 0:
        return RouteResult(domain=best_domain, method="keyword")
    return RouteResult(domain=FALLBACK_DOMAIN, method="fallback")
