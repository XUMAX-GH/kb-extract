"""Taxonomy config data model tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kb_extract.wiki.taxonomy import Category, TaxonomyConfig, load_taxonomy, save_taxonomy

pytestmark = pytest.mark.disable_socket


def test_category_frozen() -> None:
    c = Category(slug="mechanical", title="Mechanical", prd_headings=("Mechanical",),
                 linked_specs=("M9000010*",), keywords=("hinge", "bounce"))
    with pytest.raises(AttributeError):
        c.slug = "other"  # type: ignore[misc]


def test_taxonomy_config_from_dict_roundtrip(tmp_path: Path) -> None:
    cfg = TaxonomyConfig(
        version=1,
        source_prd="BC PRD",
        categories=(
            Category(slug="mechanical", title="Mechanical",
                     prd_headings=("Mechanical",), linked_specs=("M9000010*",),
                     keywords=("hinge",)),
            Category(slug="electrical", title="Electrical",
                     prd_headings=("Electrical",), linked_specs=(),
                     keywords=("power",)),
        ),
    )
    out = tmp_path / "taxonomy.json"
    save_taxonomy(cfg, out)
    loaded = load_taxonomy(out)
    assert loaded == cfg
    assert loaded.version == 1
    assert len(loaded.categories) == 2
    assert loaded.categories[0].slug == "mechanical"


def test_load_taxonomy_rejects_bad_version(tmp_path: Path) -> None:
    p = tmp_path / "taxonomy.json"
    p.write_text(json.dumps({"version": 99, "source_prd": "x", "categories": []}),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_taxonomy(p)


def test_load_taxonomy_rejects_duplicate_slugs(tmp_path: Path) -> None:
    cat = {"slug": "a", "title": "A", "prd_headings": [], "linked_specs": [], "keywords": []}
    p = tmp_path / "taxonomy.json"
    p.write_text(json.dumps({"version": 1, "source_prd": "x", "categories": [cat, cat]}),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_taxonomy(p)


def test_load_taxonomy_rejects_empty_slug(tmp_path: Path) -> None:
    cat = {"slug": "", "title": "A", "prd_headings": [], "linked_specs": [], "keywords": []}
    p = tmp_path / "taxonomy.json"
    p.write_text(json.dumps({"version": 1, "source_prd": "x", "categories": [cat]}),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="slug"):
        load_taxonomy(p)
