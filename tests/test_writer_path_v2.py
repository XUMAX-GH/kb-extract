"""PR-C: writer footnote path generalization for hierarchical paths."""
from __future__ import annotations

import pytest

from kb_extract.wiki.providers.mock import get_provider
from kb_extract.wiki.topics import EvidenceRef, Topic
from kb_extract.wiki.writer import build_topic_markdown

pytestmark = pytest.mark.disable_socket


def _ev(doc_id: str, anchor: str, title: str) -> EvidenceRef:
    return EvidenceRef(doc_id=doc_id, anchor=anchor,
                       section_title=title, page_start=1, page_end=2)


def _topic() -> Topic:
    return Topic(slug="tweeter", title="Tweeter",
                 evidence=(_ev("M9000003 Speaker PES", "a1", "Tweeter Spec"),))


def test_writer_default_uses_one_level_up() -> None:
    entry = build_topic_markdown(_topic(), get_provider("mock", seed=0))
    assert "../kb/M9000003 Speaker PES/main.md#a1" in entry.markdown


def test_writer_category_slug_uses_two_levels_up() -> None:
    entry = build_topic_markdown(_topic(), get_provider("mock", seed=0),
                                 category_slug="audio")
    assert "../../kb/M9000003 Speaker PES/main.md#a1" in entry.markdown


def test_writer_category_path_depth_2_uses_three_levels_up() -> None:
    entry = build_topic_markdown(
        _topic(), get_provider("mock", seed=0),
        category_path=("audio", "speaker"),
    )
    assert "../../../kb/M9000003 Speaker PES/main.md#a1" in entry.markdown


def test_writer_category_path_depth_3_uses_four_levels_up() -> None:
    entry = build_topic_markdown(
        _topic(), get_provider("mock", seed=0),
        category_path=("audio", "speaker", "tweeter"),
    )
    assert "../../../../kb/M9000003 Speaker PES/main.md#a1" in entry.markdown


def test_writer_category_path_depth_4_uses_five_levels_up() -> None:
    entry = build_topic_markdown(
        _topic(), get_provider("mock", seed=0),
        category_path=("audio", "speaker", "tweeter", "frequency-response"),
    )
    assert "../../../../../kb/M9000003 Speaker PES/main.md#a1" in entry.markdown


def test_writer_category_path_overrides_category_slug() -> None:
    """When both are passed, category_path takes precedence."""
    entry = build_topic_markdown(
        _topic(), get_provider("mock", seed=0),
        category_slug="ignored",
        category_path=("a", "b"),
    )
    assert "../../../kb/" in entry.markdown


def test_writer_empty_category_path_treated_as_no_category() -> None:
    """Empty tuple = depth 0 = behaves like flat."""
    entry = build_topic_markdown(
        _topic(), get_provider("mock", seed=0),
        category_path=(),
    )
    assert "../kb/M9000003 Speaker PES/main.md#a1" in entry.markdown
