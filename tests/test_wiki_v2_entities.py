from __future__ import annotations

from pathlib import Path

import pytest

from kb_extract.wiki.orchestrator import build_wiki_v2
from kb_extract.wiki.taxonomy import generate_taxonomy_v2
from tests.test_wiki_v2_e2e import _build_scene

pytestmark = pytest.mark.disable_socket


def test_build_writes_entity_pages_when_cross_domain(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD", pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0,
                  build_date="2026-06-25")
    ent_dir = project / "wiki" / "entities"
    assert ent_dir.is_dir(), "expected cross-domain entity pages to be written"
    pages = list(ent_dir.glob("*.md"))
    assert pages
    text = pages[0].read_text(encoding="utf-8")
    assert "## Appears in" in text
    assert text.startswith("---\n")
