"""Tests for generate_taxonomy_v2 (PR-B): PRD H1/H2 + PES mounting."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.taxonomy import (
    TaxonomyConfigV2,
    generate_taxonomy_v2,
)

pytestmark = pytest.mark.disable_socket


def _write_prd(kb_root: Path, doc_id: str = "BC PRD") -> Path:
    prd_dir = kb_root / doc_id
    prd_dir.mkdir(parents=True)
    index = {
        "node_id": "root", "title": "", "anchor": "", "level": 0,
        "page_start": 1, "page_end": 50,
        "children": [
            {"node_id": "ch1", "title": "Audio", "anchor": "sec-0001",
             "level": 1, "page_start": 1, "page_end": 20, "children": [
                 {"node_id": "s1", "title": "Speaker", "anchor": "sec-0002",
                  "level": 2, "page_start": 2, "page_end": 5, "children": []},
                 {"node_id": "s2", "title": "Microphone", "anchor": "sec-0003",
                  "level": 2, "page_start": 6, "page_end": 10, "children": []},
             ]},
            {"node_id": "ch2", "title": "Notification", "anchor": "sec-0010",
             "level": 1, "page_start": 21, "page_end": 40, "children": [
                 {"node_id": "s3", "title": "Speaker", "anchor": "sec-0011",
                  "level": 2, "page_start": 22, "page_end": 25, "children": []},
             ]},
        ],
    }
    (prd_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    main_md = (
        '<a id="sec-0001"></a>\n# Audio\n\n'
        "## Reference Documents\n\n| Document | Number |\n|---|---|\n"
        "| Speaker PES | M9000003 Rev A |\n\n"
        '<a id="sec-0010"></a>\n# Notification\n\n'
        "## Reference Documents\n\n| Document | Number |\n|---|---|\n"
        "| Notification Speaker PES | M2222222 |\n"
    )
    (prd_dir / "main.md").write_text(main_md, encoding="utf-8")
    return prd_dir


def _write_pes(kb_root: Path, doc_id: str, sections: list[tuple[str, list[str]]]) -> None:
    """Create a PES with H1 entries each having a list of H2 children titles."""
    pes_dir = kb_root / doc_id
    pes_dir.mkdir(parents=True)
    children = []
    for i, (h1, h2s) in enumerate(sections):
        h1_anchor = f"pes-{i:04d}"
        h2_children = [
            {"node_id": f"h2-{i}-{j}", "title": h2,
             "anchor": f"pes-{i}-{j:04d}", "level": 2,
             "page_start": 1, "page_end": 2, "children": []}
            for j, h2 in enumerate(h2s)
        ]
        children.append({
            "node_id": f"h1-{i}", "title": h1, "anchor": h1_anchor,
            "level": 1, "page_start": 1, "page_end": 10, "children": h2_children,
        })
    index = {"node_id": "root", "title": "", "anchor": "", "level": 0,
             "page_start": 1, "page_end": 50, "children": children}
    (pes_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (pes_dir / "main.md").write_text("# " + doc_id + "\n", encoding="utf-8")


def test_generate_v2_returns_taxonomy_v2(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _write_prd(kb_root)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD")
    assert isinstance(cfg, TaxonomyConfigV2)
    assert cfg.version == 2
    assert cfg.source_prd == "BC PRD"
    assert cfg.source_pes_glob is None


def test_generate_v2_prd_only_creates_system_subsystem(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _write_prd(kb_root)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD")
    # Two PRD H1 -> two system nodes
    assert len(cfg.categories) == 2
    slugs = [c.slug for c in cfg.categories]
    assert "audio" in slugs and "notification" in slugs
    for sys_node in cfg.categories:
        assert sys_node.layer == "system"
        for sub in sys_node.children:
            assert sub.layer == "subsystem"
            # No part / function without PES
            assert sub.children == ()
    audio = next(c for c in cfg.categories if c.slug == "audio")
    sub_slugs = sorted(s.slug for s in audio.children)
    assert sub_slugs == ["microphone", "speaker"]


def test_generate_v2_no_pes_glob_keeps_source_pes_glob_none(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _write_prd(kb_root)
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD")
    assert cfg.source_pes_glob is None


def test_generate_v2_with_pes_glob_records_pattern(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _write_prd(kb_root)
    cfg = generate_taxonomy_v2(
        kb_root, prd_doc_id="BC PRD", pes_glob="*PES*"
    )
    assert cfg.source_pes_glob == "*PES*"


def test_generate_v2_mounts_pes_under_matching_subsystem(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _write_prd(kb_root)
    # Speaker PES referenced as M9000003 under Audio in PRD
    _write_pes(kb_root, "M9000003 Speaker PES",
               [("Tweeter", ["Frequency Response", "SPL"]),
                ("Woofer", ["Resonance"])])
    cfg = generate_taxonomy_v2(
        kb_root, prd_doc_id="BC PRD", pes_glob="M9000003*"
    )
    audio = next(c for c in cfg.categories if c.slug == "audio")
    # Audio has subsystem speaker (PRD) and subsystem microphone (PRD).
    # The Speaker PES should mount under audio/speaker.
    speaker = next(s for s in audio.children if s.slug == "speaker")
    part_slugs = sorted(p.slug for p in speaker.children)
    assert "tweeter" in part_slugs
    assert "woofer" in part_slugs
    for part in speaker.children:
        assert part.layer == "part"
        for fn in part.children:
            assert fn.layer == "function"
    tweeter = next(p for p in speaker.children if p.slug == "tweeter")
    fn_slugs = sorted(f.slug for f in tweeter.children)
    assert "frequency-response" in fn_slugs
    assert "spl" in fn_slugs


def test_generate_v2_does_not_merge_same_name_part_across_subsystems(
    tmp_path: Path,
) -> None:
    """Spec: cross-PES same-name part NOT merged across subsystems."""
    kb_root = tmp_path / "kb"
    _write_prd(kb_root)
    # Same `Tweeter` part name in both Audio Speaker PES and Notification PES
    _write_pes(kb_root, "M9000003 Speaker PES", [("Tweeter", ["A"])])
    _write_pes(kb_root, "M2222222 Notification Speaker PES", [("Tweeter", ["B"])])
    cfg = generate_taxonomy_v2(
        kb_root, prd_doc_id="BC PRD", pes_glob="M*"
    )
    audio = next(c for c in cfg.categories if c.slug == "audio")
    notif = next(c for c in cfg.categories if c.slug == "notification")
    audio_speaker = next(s for s in audio.children if s.slug == "speaker")
    notif_speaker = next(s for s in notif.children if s.slug == "speaker")
    a_tweeter = next(p for p in audio_speaker.children if p.slug == "tweeter")
    n_tweeter = next(p for p in notif_speaker.children if p.slug == "tweeter")
    # Each tweeter has its own function children, not merged
    assert [f.slug for f in a_tweeter.children] == ["a"]
    assert [f.slug for f in n_tweeter.children] == ["b"]


def test_generate_v2_pes_glob_no_match_yields_no_parts(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _write_prd(kb_root)
    _write_pes(kb_root, "Z9999999 Unrelated", [("Foo", [])])
    cfg = generate_taxonomy_v2(
        kb_root, prd_doc_id="BC PRD", pes_glob="Z9999999*"
    )
    for sys_node in cfg.categories:
        for sub in sys_node.children:
            assert sub.children == ()


def test_generate_v2_is_deterministic(tmp_path: Path) -> None:
    kb_root = tmp_path / "kb"
    _write_prd(kb_root)
    _write_pes(kb_root, "M9000003 Speaker PES",
               [("Tweeter", ["A", "B"]), ("Woofer", [])])
    cfg1 = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                                pes_glob="M*")
    cfg2 = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                                pes_glob="M*")
    assert cfg1.to_dict() == cfg2.to_dict()


def test_generate_v2_validates_h21(tmp_path: Path) -> None:
    """Returned config must satisfy H21 invariants (depth, layer, uniqueness)."""
    kb_root = tmp_path / "kb"
    _write_prd(kb_root)
    _write_pes(kb_root, "M9000003 Speaker PES",
               [("Tweeter", ["A"]), ("Woofer", ["B"])])
    cfg = generate_taxonomy_v2(kb_root, prd_doc_id="BC PRD",
                               pes_glob="M*")
    from kb_extract.wiki.taxonomy import validate_taxonomy_v2
    validate_taxonomy_v2(cfg)  # no raise
