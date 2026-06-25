"""Task 8: verify that v2 topic pages are prefixed with YAML frontmatter."""
from __future__ import annotations

from pathlib import Path

import pytest

from kb_extract.wiki.orchestrator import build_wiki_v2
from kb_extract.wiki.taxonomy import generate_taxonomy_v2
from tests.test_wiki_v2_e2e import _build_scene

pytestmark = pytest.mark.disable_socket


def test_v2_topic_pages_have_frontmatter(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD", pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0)
    pages = [p for p in (project / "wiki").rglob("*.md")
             if p.name != "_index.md"]
    assert pages, "expected at least one topic page"
    text = pages[0].read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "category_path:" in text
    assert "tags:" in text
