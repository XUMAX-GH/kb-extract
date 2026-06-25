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

from ..serialization import serialize_markdown
from .frontmatter import build_frontmatter, render_frontmatter
from .providers.base import LlmClient, Message
from .wikilink import to_wikilink


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


def _summary_messages(cand: Candidate) -> list[Message]:
    sys: Message = {
        "role": "system",
        "content": (
            "You are maintaining a cross-domain knowledge wiki. Write a short "
            "(2-4 sentence) synthesis describing what this shared source covers "
            "and why it connects the listed domains. Do not invent specifics; "
            "stay general if unsure. No markdown headings."
        ),
    }
    user: Message = {
        "role": "user",
        "content": (
            f"Shared source: {cand.key}\n"
            f"Connected domains: {', '.join(cand.domains)}\n"
            f"Referenced by topics: {', '.join(cand.backlinks)}"
        ),
    }
    return [sys, user]


def render_entity_page(cand: Candidate, llm: LlmClient) -> str:
    """Render one entity/concept aggregation page (frontmatter + summary +
    sorted wikilink backlinks)."""
    summary = llm.chat(_summary_messages(cand)).strip()
    fm = render_frontmatter(build_frontmatter(
        title=cand.key,
        category_path=(cand.kind,),
        slug=cand.key,
        doc_ids=[cand.key],
        page_type=cand.kind,
        extra_tags=[f"domain/{d}" for d in cand.domains],
    ))
    lines = [
        fm.rstrip("\n"),
        "",
        f"# {cand.key}",
        "",
        summary,
        "",
        "## Appears in",
        "",
    ]
    for link in cand.backlinks:
        label = link.rsplit("/", 1)[-1]
        lines.append(f"- {to_wikilink(link, label)}")
    lines.append("")
    return serialize_markdown("\n".join(lines))
