"""PR-C: end-to-end v2 wiki build (hierarchical layout + recursive _index.md)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.orchestrator import build_wiki_v2, verify_wiki
from kb_extract.wiki.taxonomy import generate_taxonomy_v2

pytestmark = pytest.mark.disable_socket


def _write_doc(
    kb_root: Path,
    doc_id: str,
    *,
    source_path: str,
    sha: str,
    index: dict,
    main_md: str,
) -> None:
    d = kb_root / doc_id
    d.mkdir(parents=True)
    (d / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (d / "main.md").write_text(main_md, encoding="utf-8")
    meta = {"doc_id": doc_id, "source_path": source_path,
            "source_sha256": sha, "tool_version": "test"}
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _make_manifest(kb_root: Path, items: list[tuple[str, str]]) -> None:
    """Build a minimal manifest.sqlite with (source_path, source_sha256)."""
    import sqlite3
    db = kb_root / "manifest.sqlite"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "CREATE TABLE sources (source_path TEXT PRIMARY KEY, source_sha256 TEXT)"
        )
        conn.executemany(
            "INSERT INTO sources(source_path, source_sha256) VALUES (?, ?)", items,
        )
        conn.commit()
    finally:
        conn.close()


def _build_scene(tmp_path: Path) -> tuple[Path, Path]:
    """PRD with 2 systems x 2 subsystems, plus one PES mounted under Audio/Speaker."""
    project = tmp_path / "proj"
    kb_root = project / "kb"
    kb_root.mkdir(parents=True)

    prd_doc_id = "BC PRD"
    prd_index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 50,
        "children": [
            {"node_id": "ch1", "title": "Audio", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 20,
             "children": [
                 {"node_id": "s1", "title": "Speaker", "anchor": "sec-0002",
                  "level": 2, "page_start": 2, "page_end": 5, "children": []},
                 {"node_id": "s2", "title": "Microphone", "anchor": "sec-0003",
                  "level": 2, "page_start": 6, "page_end": 10, "children": []},
             ]},
            {"node_id": "ch2", "title": "Electrical", "anchor": "sec-0010",
             "level": 1, "page_start": 21, "page_end": 40,
             "children": [
                 {"node_id": "s3", "title": "Power", "anchor": "sec-0011",
                  "level": 2, "page_start": 22, "page_end": 25, "children": []},
             ]},
        ],
    }
    prd_main = (
        '<a id="sec-0001"></a>\n# Audio\n\n'
        "## Reference Documents\n\n| Document | Number |\n|---|---|\n"
        "| Speaker PES | M9000003 Rev A |\n\n"
        '<a id="sec-0002"></a>\n## Speaker\n\nText about speaker.\n\n'
        '<a id="sec-0003"></a>\n## Microphone\n\nText about microphone.\n\n'
        '<a id="sec-0010"></a>\n# Electrical\n\n'
        '<a id="sec-0011"></a>\n## Power\n\nPower supply spec.\n'
    )
    _write_doc(kb_root, prd_doc_id, source_path="BC PRD.pdf",
               sha="prd-sha", index=prd_index, main_md=prd_main)

    pes_doc_id = "M9000003 Speaker PES"
    pes_index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 30,
        "children": [
            {"node_id": "h1-0", "title": "Tweeter", "anchor": "pes-0001",
             "level": 1, "page_start": 1, "page_end": 10,
             "children": [
                 {"node_id": "h2-0", "title": "Frequency Response",
                  "anchor": "pes-0002", "level": 2,
                  "page_start": 2, "page_end": 4, "children": []},
                 {"node_id": "h2-1", "title": "SPL", "anchor": "pes-0003",
                  "level": 2, "page_start": 5, "page_end": 6, "children": []},
             ]},
        ],
    }
    pes_main = (
        '<a id="pes-0001"></a>\n# Tweeter\n\n'
        '<a id="pes-0002"></a>\n## Frequency Response\n\n'
        '<a id="pes-0003"></a>\n## SPL\n\n'
    )
    _write_doc(kb_root, pes_doc_id, source_path="M9000003 Speaker PES.pdf",
               sha="pes-sha", index=pes_index, main_md=pes_main)

    _make_manifest(kb_root,
                   [("BC PRD.pdf", "prd-sha"),
                    ("M9000003 Speaker PES.pdf", "pes-sha")])
    return project, kb_root


def test_build_wiki_v2_creates_hierarchical_layout(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                               pes_glob="M*")
    result = build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0)
    wiki = project / "wiki"

    # Root index
    assert (wiki / "_index.md").is_file()
    # System index
    assert (wiki / "audio" / "_index.md").is_file()
    assert (wiki / "electrical" / "_index.md").is_file()
    # Subsystem index
    assert (wiki / "audio" / "speaker" / "_index.md").is_file()
    # Part index (since tweeter has function children)
    assert (wiki / "audio" / "speaker" / "tweeter" / "_index.md").is_file()
    # At least one terminal topic .md exists
    md_files = list(wiki.rglob("*.md"))
    assert any(p.name != "_index.md" for p in md_files)
    assert result.unresolved_total == 0


def test_build_wiki_v2_evidence_routed_to_deepest_path(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                               pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0)
    # Tweeter Frequency Response evidence should land under
    # wiki/audio/speaker/tweeter/frequency-response/*.md
    deep_dir = project / "wiki" / "audio" / "speaker" / "tweeter" / "frequency-response"
    assert deep_dir.is_dir()
    topics = [p for p in deep_dir.glob("*.md") if p.name != "_index.md"]
    assert len(topics) >= 1


def test_build_wiki_v2_footnote_uses_correct_depth(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                               pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0)
    # 4-deep path -> "../../../../../kb"
    deep_dir = project / "wiki" / "audio" / "speaker" / "tweeter" / "frequency-response"
    topics = [p for p in deep_dir.glob("*.md") if p.name != "_index.md"]
    body = topics[0].read_text(encoding="utf-8")
    # 4-layer depth means 5 ups (4 for path + 1 to escape wiki/)
    assert "../../../../../kb/" in body


def test_build_wiki_v2_deterministic(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                               pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0)
    first = sorted(
        (p.relative_to(project).as_posix(), p.read_bytes())
        for p in (project / "wiki").rglob("*")
        if p.is_file()
    )

    # Rebuild
    project2 = tmp_path / "proj2"
    # Copy kb tree
    import shutil
    shutil.copytree(kb_root, project2 / "kb")
    cfg2 = generate_taxonomy_v2(project2 / "kb",
                                prd_doc_id="BC PRD", pes_glob="M*")
    build_wiki_v2(project2, taxonomy=cfg2, provider="mock", seed=0)
    second = sorted(
        (p.relative_to(project2).as_posix(), p.read_bytes())
        for p in (project2 / "wiki").rglob("*")
        if p.is_file()
    )
    assert first == second


def test_build_wiki_v2_verify_passes(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                               pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0)
    violations = verify_wiki(project)
    assert violations == [], violations


def test_root_index_lists_all_systems(tmp_path: Path) -> None:
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                               pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0)
    root_idx = (project / "wiki" / "_index.md").read_text(encoding="utf-8")
    assert "Audio" in root_idx
    assert "Electrical" in root_idx
    # Links to child folders
    assert "audio/_index" in root_idx


def test_root_index_reports_actual_provider(tmp_path: Path) -> None:
    """The v2 root _index.md header must reflect the provider actually used,
    not a hardcoded value (regression: header was always 'provider=mock')."""
    project, kb_root = _build_scene(tmp_path)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                               pes_glob="M*")
    build_wiki_v2(project, taxonomy=cfg, provider="mock", seed=0)
    root_idx = (project / "wiki" / "_index.md").read_text(encoding="utf-8")
    assert "provider=mock" in root_idx

    # A different provider must surface in the header rather than 'mock'.
    project2, kb_root2 = _build_scene(tmp_path / "p2")
    cfg2 = generate_taxonomy_v2(kb_root2, prd_doc_id="BC PRD",
                                pes_glob="M*")

    class _NamedClient:
        name = "cached"

        def chat(self, messages: list) -> str:
            return "body [^ev-1]"

    build_wiki_v2(project2, taxonomy=cfg2, provider=_NamedClient(), seed=0)
    root_idx2 = (project2 / "wiki" / "_index.md").read_text(encoding="utf-8")
    assert "provider=cached" in root_idx2
    assert "provider=mock" not in root_idx2
