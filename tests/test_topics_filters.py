"""Tests for v0.6.0 topic discovery filters: min_evidence, skip_numeric_titles."""

from __future__ import annotations

import json
from pathlib import Path


def _write_index(doc_dir: Path, children: list[dict]) -> None:
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "index.json").write_text(
        json.dumps({"title": "root", "children": children}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_min_evidence_filter_keeps_only_topics_with_enough_evidence(tmp_path: Path) -> None:
    """``min_evidence=2`` should drop topics with only one evidence ref."""
    from kb_extract.wiki.topics import discover_topics

    kb_root = tmp_path / "kb"
    # Two docs share an "approvals" section -> 2 evidence, kept.
    _write_index(
        kb_root / "docA",
        [{"title": "Approvals", "anchor": "sec-1", "page_start": 1, "page_end": 1}],
    )
    _write_index(
        kb_root / "docB",
        [{"title": "Approvals", "anchor": "sec-2", "page_start": 1, "page_end": 1}],
    )
    # Only one doc has "Singleton" -> 1 evidence, dropped at min_evidence=2.
    _write_index(
        kb_root / "docC",
        [{"title": "Singleton", "anchor": "sec-3", "page_start": 1, "page_end": 1}],
    )

    topics = discover_topics(tmp_path, output_dir=tmp_path, min_evidence=2)
    slugs = {t.slug for t in topics}
    assert "approvals" in slugs
    assert "singleton" not in slugs


def test_min_evidence_defaults_to_1_for_back_compat(tmp_path: Path) -> None:
    """Without explicit min_evidence, behavior matches v0.5.x (keep singletons)."""
    from kb_extract.wiki.topics import discover_topics

    kb_root = tmp_path / "kb"
    _write_index(
        kb_root / "docA",
        [{"title": "Singleton", "anchor": "sec-1", "page_start": 1, "page_end": 1}],
    )
    topics = discover_topics(tmp_path, output_dir=tmp_path)
    assert any(t.slug == "singleton" for t in topics)


def test_skip_numeric_titles_drops_section_titled_just_a_number(tmp_path: Path) -> None:
    """Sections titled "1" / "1.4" / "2.3.1" carry no semantic value."""
    from kb_extract.wiki.topics import discover_topics

    kb_root = tmp_path / "kb"
    _write_index(
        kb_root / "docA",
        [
            {"title": "1", "anchor": "sec-1", "page_start": 1, "page_end": 1},
            {"title": "1.4", "anchor": "sec-2", "page_start": 2, "page_end": 2},
            {"title": "Compliance", "anchor": "sec-3", "page_start": 3, "page_end": 3},
        ],
    )

    topics = discover_topics(tmp_path, output_dir=tmp_path, skip_numeric_titles=True)
    slugs = {t.slug for t in topics}
    # The bare-numeric titles should be filtered out
    assert "1" not in slugs
    assert "1-4" not in slugs
    # Semantic title is kept
    assert "compliance" in slugs


def test_skip_numeric_titles_false_keeps_them(tmp_path: Path) -> None:
    """Default behavior preserves all titles (back-compat)."""
    from kb_extract.wiki.topics import discover_topics

    kb_root = tmp_path / "kb"
    _write_index(
        kb_root / "docA",
        [{"title": "1.4", "anchor": "sec-1", "page_start": 1, "page_end": 1}],
    )
    topics = discover_topics(tmp_path, output_dir=tmp_path)
    assert any(t.slug == "1-4" or t.title == "1.4" for t in topics)


def test_combined_filters_remove_only_what_was_specified(tmp_path: Path) -> None:
    """Both filters apply together: must meet min_evidence AND non-numeric title."""
    from kb_extract.wiki.topics import discover_topics

    kb_root = tmp_path / "kb"
    # 2 docs share "Compliance" -> kept by both filters
    _write_index(
        kb_root / "docA",
        [
            {"title": "Compliance", "anchor": "sec-1a", "page_start": 1, "page_end": 1},
            {"title": "1", "anchor": "sec-2a", "page_start": 2, "page_end": 2},
        ],
    )
    _write_index(
        kb_root / "docB",
        [
            {"title": "Compliance", "anchor": "sec-1b", "page_start": 1, "page_end": 1},
            {"title": "1", "anchor": "sec-2b", "page_start": 2, "page_end": 2},
        ],
    )

    topics = discover_topics(
        tmp_path,
        output_dir=tmp_path,
        min_evidence=2,
        skip_numeric_titles=True,
    )
    slugs = {t.slug for t in topics}
    assert "compliance" in slugs
    # "1" topic has 2 evidence (both docs) but title is numeric -> dropped
    assert "1" not in slugs
