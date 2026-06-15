"""Tests for v1 -> v2 taxonomy schema migrator (PR-A)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.taxonomy import (
    CategoryNode,
    load_taxonomy_v2,
    migrate_v1_to_v2,
    save_taxonomy_v2,
)

pytestmark = pytest.mark.disable_socket


def _v1_empty() -> dict:
    return {"version": 1, "source_prd": "doc-prd", "categories": []}


def _v1_single() -> dict:
    return {
        "version": 1,
        "source_prd": "doc-prd",
        "categories": [
            {
                "slug": "audio",
                "title": "Audio System",
                "prd_headings": ["Audio System", "Audio System / Speaker"],
                "linked_specs": ["PES-Audio-*"],
                "keywords": ["audio", "sound"],
            }
        ],
    }


def test_migrate_empty_categories() -> None:
    v2 = migrate_v1_to_v2(_v1_empty())
    assert v2["version"] == 2
    assert v2["categories"] == []
    assert v2["source_prd"] == "doc-prd"
    assert v2["source_pes_glob"] is None


def test_migrate_single_category_becomes_system_layer() -> None:
    v2 = migrate_v1_to_v2(_v1_single())
    assert v2["version"] == 2
    assert len(v2["categories"]) == 1
    cat = v2["categories"][0]
    assert cat["layer"] == "system"
    assert cat["children"] == []
    assert cat["pes_headings"] == []
    # v1 fields preserved verbatim
    assert cat["slug"] == "audio"
    assert cat["prd_headings"] == ["Audio System", "Audio System / Speaker"]
    assert cat["linked_specs"] == ["PES-Audio-*"]
    assert cat["keywords"] == ["audio", "sound"]


def test_migrate_multi_category_all_system_layer() -> None:
    v1 = {
        "version": 1,
        "source_prd": "doc-prd",
        "categories": [
            {"slug": "a", "title": "A", "prd_headings": ["A"],
             "linked_specs": [], "keywords": []},
            {"slug": "b", "title": "B", "prd_headings": ["B"],
             "linked_specs": [], "keywords": []},
        ],
    }
    v2 = migrate_v1_to_v2(v1)
    assert all(c["layer"] == "system" for c in v2["categories"])
    assert all(c["children"] == [] for c in v2["categories"])


def test_migrate_idempotent_on_v2_input() -> None:
    v2 = migrate_v1_to_v2(_v1_single())
    again = migrate_v1_to_v2(v2)
    assert again == v2


def test_load_taxonomy_v2_auto_migrates_v1_file(tmp_path: Path) -> None:
    fp = tmp_path / "taxonomy.json"
    fp.write_text(json.dumps(_v1_single()), encoding="utf-8")
    cfg = load_taxonomy_v2(fp)
    assert cfg.version == 2
    assert len(cfg.categories) == 1
    assert cfg.categories[0].layer == "system"
    assert cfg.categories[0].slug == "audio"
    assert cfg.categories[0].children == ()


def test_load_taxonomy_v2_reads_native_v2_file(tmp_path: Path) -> None:
    fp = tmp_path / "taxonomy.json"
    fp.write_text(
        json.dumps({
            "version": 2,
            "source_prd": "doc-prd",
            "source_pes_glob": "PES-*",
            "categories": [
                CategoryNode(
                    slug="audio", title="Audio", layer="system",
                    children=(CategoryNode(
                        slug="speaker", title="Speaker", layer="subsystem",
                    ),),
                ).to_dict()
            ],
        }),
        encoding="utf-8",
    )
    cfg = load_taxonomy_v2(fp)
    assert cfg.version == 2
    assert cfg.categories[0].children[0].slug == "speaker"


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    from kb_extract.wiki.taxonomy import TaxonomyConfigV2
    cfg = TaxonomyConfigV2(
        version=2,
        source_prd="doc-prd",
        source_pes_glob="PES-*",
        categories=(
            CategoryNode(
                slug="audio", title="Audio", layer="system",
                children=(CategoryNode(
                    slug="speaker", title="Speaker", layer="subsystem",
                ),),
            ),
        ),
    )
    fp = tmp_path / "taxonomy.json"
    save_taxonomy_v2(cfg, fp)
    loaded = load_taxonomy_v2(fp)
    assert loaded == cfg


def test_save_v2_deterministic_bytes(tmp_path: Path) -> None:
    from kb_extract.wiki.taxonomy import TaxonomyConfigV2
    cfg = TaxonomyConfigV2(
        version=2, source_prd="doc-prd", source_pes_glob=None,
        categories=(CategoryNode(slug="x", title="X", layer="system"),),
    )
    fp1 = tmp_path / "a.json"
    fp2 = tmp_path / "b.json"
    save_taxonomy_v2(cfg, fp1)
    save_taxonomy_v2(cfg, fp2)
    assert fp1.read_bytes() == fp2.read_bytes()
