"""sp3 测试：topic 聚类（无 LLM、纯算法）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.topics import discover_topics

pytestmark = pytest.mark.disable_socket


def _write_index(doc_dir: Path, root: dict) -> None:
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "index.json").write_text(json.dumps(root), encoding="utf-8")
    # 写一个空 main.md，让 walk 不报错（即便不强制需要）
    (doc_dir / "main.md").write_text("# stub\n", encoding="utf-8")


def _leaf(title: str, anchor: str, page: int = 1) -> dict:
    return {"node_id": anchor, "title": title, "anchor": anchor, "page_start": page,
            "page_end": page, "level": 1, "children": []}


def _root(*leaves: dict) -> dict:
    return {"node_id": "root", "title": "", "anchor": "", "page_start": 1,
            "page_end": 99, "level": 0, "children": list(leaves)}


def test_discover_topics_returns_empty_when_no_kb_dir(tmp_path: Path) -> None:
    assert discover_topics(tmp_path) == []


def test_discover_topics_groups_titles_with_overlapping_keywords(tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    _write_index(kb / "doc1", _root(
        _leaf("thermal management design", "a1"),
        _leaf("thermal materials selection", "a2"),
        _leaf("power supply requirements", "a3"),
    ))
    topics = discover_topics(tmp_path)
    # "thermal" 出现两次，应该形成一个簇；power 单独一个
    titles = [t.title for t in topics]
    assert any("thermal" in t.lower() for t in titles)
    assert any("power" in t.lower() or "supply" in t.lower() for t in titles)


def test_discover_topics_is_deterministic(tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    _write_index(kb / "doc1", _root(
        _leaf("alpha beta", "a1"),
        _leaf("alpha gamma", "a2"),
        _leaf("delta epsilon", "a3"),
    ))
    out1 = discover_topics(tmp_path)
    out2 = discover_topics(tmp_path)
    assert [(t.slug, t.title, [(e.anchor) for e in t.evidence]) for t in out1] == \
           [(t.slug, t.title, [(e.anchor) for e in t.evidence]) for t in out2]


def test_discover_topics_multiple_docs_share_topic(tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    _write_index(kb / "doc1", _root(_leaf("battery thermal limits", "a1")))
    _write_index(kb / "doc2", _root(_leaf("battery cell thermal", "b1")))
    topics = discover_topics(tmp_path)
    # 跨文档共享词 -> 应被合并到同一个 topic
    big_topic = max(topics, key=lambda t: len(t.evidence))
    doc_ids = {ev.doc_id for ev in big_topic.evidence}
    assert {"doc1", "doc2"} <= doc_ids
