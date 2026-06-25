import dataclasses

import pytest

from kb_extract.wiki.entities import Candidate, extract_candidates


def test_extract_candidates_finds_cross_domain_doc_ids():
    # Two topics in different domains both cite doc M1041012 -> cross-domain.
    topics = [
        {"slug": "hinge", "title": "Hinge", "domain": "mechanical",
         "category_path": "bc/mechanical",
         "evidence_doc_ids": ["M1041012", "M1320722"]},
        {"slug": "battery", "title": "Battery", "domain": "electrical",
         "category_path": "bc/electrical",
         "evidence_doc_ids": ["M1041012"]},
        {"slug": "boot", "title": "Boot", "domain": "software",
         "category_path": "bc/software",
         "evidence_doc_ids": ["M9999999"]},
    ]
    cands = extract_candidates(topics, min_domains=2)
    by_key = {c.key: c for c in cands}
    # M1041012 spans mechanical + electrical -> candidate.
    assert "M1041012" in by_key
    assert sorted(by_key["M1041012"].domains) == ["electrical", "mechanical"]
    # M1320722 + M9999999 appear in only one domain -> excluded.
    assert "M1320722" not in by_key
    assert "M9999999" not in by_key
    # Backlinks sorted + deterministic.
    assert by_key["M1041012"].backlinks == tuple(sorted(by_key["M1041012"].backlinks))


def test_candidate_is_frozen_dataclass():
    c = Candidate(key="X", kind="entity", domains=("a", "b"),
                  backlinks=("bc/a/x", "bc/b/y"))
    assert c.key == "X"
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.key = "Y"
