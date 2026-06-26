from __future__ import annotations

from pathlib import Path

import pytest

from kb_extract.wiki.orchestrator import build_wiki_v2
from kb_extract.wiki.taxonomy import generate_taxonomy_v2
from tests.test_wiki_v2_e2e import _build_scene

pytestmark = pytest.mark.disable_socket


def test_index_pages_use_wikilinks(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD", pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0)
    root_idx = (project / "wiki" / "_index.md").read_text(encoding="utf-8")
    assert "[[" in root_idx and "]]" in root_idx
    # Old relative-md nav link form must be gone.
    assert "/_index.md)" not in root_idx
    # A per-node index has frontmatter.
    node_idx = (project / "wiki" / "audio" / "_index.md").read_text(encoding="utf-8")
    assert node_idx.startswith("---\n")
    assert "[[" in node_idx
