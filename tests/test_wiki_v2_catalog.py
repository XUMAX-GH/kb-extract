from __future__ import annotations

from pathlib import Path

import pytest

from kb_extract.wiki.orchestrator import build_wiki_v2
from kb_extract.wiki.taxonomy import generate_taxonomy_v2
from tests.test_wiki_v2_e2e import _build_scene

pytestmark = pytest.mark.disable_socket


def test_build_writes_index_and_log(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD", pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0,
                  build_date="2026-06-25")
    wiki = project / "wiki"
    assert (wiki / "index.md").is_file()
    log = (wiki / "log.md").read_text(encoding="utf-8")
    assert "## [2026-06-25] build |" in log


def test_log_is_append_only(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD", pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0,
                  build_date="2026-06-25")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0,
                  build_date="2026-06-26")
    log = (project / "wiki" / "log.md").read_text(encoding="utf-8")
    assert log.count("## [") == 2
    assert "2026-06-25" in log and "2026-06-26" in log
