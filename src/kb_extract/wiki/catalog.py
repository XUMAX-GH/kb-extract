"""Karpathy-style wiki navigation files: content catalog + chronological log.

``index.md`` is a content-oriented catalog (one line per page, grouped by
domain). ``log.md`` is an append-only chronological record; the date is
injected (never read from the wall clock) so output stays byte-reproducible.
"""

from __future__ import annotations

from collections import defaultdict

from .wikilink import to_wikilink

# row = (domain, title, slug_path_for_link, doc_ids)
CatalogRow = tuple[str, str, str, list[str]]


def render_index_md(rows: list[CatalogRow]) -> str:
    """Render the wiki catalog grouped by domain, deterministically ordered."""
    by_domain: dict[str, list[CatalogRow]] = defaultdict(list)
    for row in rows:
        by_domain[row[0]].append(row)
    lines = ["# Wiki Index", ""]
    for domain in sorted(by_domain):
        lines.append(f"## {domain}")
        lines.append("")
        for _dom, title, link_path, doc_ids in sorted(
            by_domain[domain], key=lambda r: (r[1], r[2])
        ):
            src = ", ".join(sorted(set(doc_ids)))
            suffix = f" - sources: {src}" if src else ""
            lines.append(f"- {to_wikilink(link_path, title)}{suffix}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def render_log_entry(*, date: str, provider: str, topics: int, pins: int) -> str:
    """Render one append-only log line (parseable via ``grep '^## \\['``)."""
    return f"## [{date}] build | provider={provider}, topics={topics}, pins={pins}"
