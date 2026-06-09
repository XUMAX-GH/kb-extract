"""sp3 测试：writer + evidence pin 解析。"""

from __future__ import annotations

import pytest

from kb_extract.wiki.providers.mock import MockLlmClient
from kb_extract.wiki.topics import EvidenceRef, Topic
from kb_extract.wiki.writer import build_topic_markdown

pytestmark = pytest.mark.disable_socket


def _topic(n_ev: int = 2) -> Topic:
    evs = tuple(
        EvidenceRef(
            doc_id="doc1",
            anchor=f"a{i+1}",
            section_title=f"Section {i+1}",
            page_start=i + 1,
            page_end=i + 1,
        )
        for i in range(n_ev)
    )
    return Topic(slug="test-topic", title="Test Topic", evidence=evs)


def test_writer_emits_resolved_footnote_definitions() -> None:
    topic = _topic(n_ev=3)
    llm = MockLlmClient(seed=0)
    entry = build_topic_markdown(topic, llm)
    assert "# Test Topic" in entry.markdown
    # 每个出现过的 [^ev-N] 都有对应 footnote 定义
    for n in range(1, 4):
        pin = f"[^ev-{n}]"
        if pin in entry.markdown:
            # 应该既出现在正文，也出现在 footnote 定义里（含 :)
            assert f"[^ev-{n}]:" in entry.markdown


def test_writer_links_footnotes_to_correct_anchor() -> None:
    topic = _topic(n_ev=2)
    llm = MockLlmClient(seed=0)
    entry = build_topic_markdown(topic, llm)
    # 必须能找到至少一个 footnote 指向 ../kb/doc1/main.md#a1 或 a2
    assert "../kb/doc1/main.md#a" in entry.markdown


def test_writer_unresolved_pin_is_reported() -> None:
    # 自定义 client 返回越界 pin
    class _BadClient:
        name = "bad"

        def chat(self, messages: list) -> str:
            return "claim [^ev-99] text"

    topic = _topic(n_ev=1)
    entry = build_topic_markdown(topic, _BadClient())
    assert 99 in entry.unresolved_pins
    assert "UNRESOLVED" in entry.markdown


def test_writer_raises_on_empty_evidence() -> None:
    bad_topic = Topic(slug="x", title="X", evidence=())
    with pytest.raises(ValueError):
        build_topic_markdown(bad_topic, MockLlmClient())
