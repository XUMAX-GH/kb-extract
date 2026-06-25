"""Cross-domain entity/concept aggregation for the Obsidian wiki layer.

Phase 1 (this module, deterministic): scan topic metadata for shared evidence
documents that span >= ``min_domains`` distinct domains. Each such shared doc
becomes an aggregation *candidate* with sorted backlinks to every topic that
cites it. Phase 2 (``build_aggregation_pages``) uses the cached LLM provider to
author a short synthesis per candidate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candidate:
    key: str               # the shared doc id (entity key)
    kind: str              # "entity" | "concept"
    domains: tuple[str, ...]
    backlinks: tuple[str, ...]   # category_path/slug for each citing topic


def extract_candidates(
    topics: list[dict], *, min_domains: int = 2
) -> list[Candidate]:
    """Return cross-domain aggregation candidates, sorted by key.

    ``topics`` items must carry: ``slug``, ``domain``, ``category_path``,
    ``evidence_doc_ids`` (list[str]).
    """
    domains_by_doc: dict[str, set[str]] = defaultdict(set)
    backlinks_by_doc: dict[str, set[str]] = defaultdict(set)
    for t in topics:
        link = f"{t['category_path']}/{t['slug']}"
        for doc_id in t.get("evidence_doc_ids", []):
            domains_by_doc[doc_id].add(t["domain"])
            backlinks_by_doc[doc_id].add(link)

    out: list[Candidate] = []
    for key in sorted(domains_by_doc):
        domains = domains_by_doc[key]
        if len(domains) < min_domains:
            continue
        out.append(Candidate(
            key=key,
            kind="entity",
            domains=tuple(sorted(domains)),
            backlinks=tuple(sorted(backlinks_by_doc[key])),
        ))
    return out
