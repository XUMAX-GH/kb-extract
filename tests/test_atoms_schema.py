from kb_extract.wiki.atoms.prompts import build_system_prompt
from kb_extract.wiki.atoms.schema import Atom, atom_id, coerce_atom, parse_atoms


def test_atom_id_stable_and_independent_of_value():
    a = atom_id(entity="hinge", parameter="force", condition="open", source_doc="D", section="sec-0001")
    b = atom_id(entity="Hinge", parameter="Force", condition="OPEN", source_doc="D", section="sec-0001")
    assert a == b and len(a) == 16


def test_coerce_forces_source_and_evidence():
    it = coerce_atom(
        {"entity": "Hinge", "parameter": "Force", "value": "5", "unit": "N",
         "type": "spec", "condition": "open", "source_doc": "LIE", "section": "sec-9"},
        doc_id="DOC1", anchor="sec-0001",
    )
    assert it.source_doc == "DOC1"
    assert it.section == "sec-0001"
    assert it.evidence_ref == "kb/DOC1/main.md#sec-0001"
    assert it.id == atom_id(entity="hinge", parameter="force", condition="open",
                            source_doc="DOC1", section="sec-0001")


def test_missing_value_flags_pending():
    it = coerce_atom({"entity": "pen", "parameter": "tip force", "type": "requirement"},
                     doc_id="D", anchor="sec-0002")
    assert it.value is None
    assert "待验证" in it.flags


def test_invalid_type_flagged_pending():
    it = coerce_atom({"entity": "x", "parameter": "y", "value": "1", "type": "bogus"},
                     doc_id="D", anchor="sec-1")
    assert it.type == "spec"
    assert "待验证" in it.flags


def test_parse_atoms_strips_fence():
    out = parse_atoms('```json\n[{"entity":"a","parameter":"b"}]\n```')
    assert out == [{"entity": "a", "parameter": "b"}]


def test_to_dict_sorted_flags_and_confidence_rounded():
    it = coerce_atom({"entity": "a", "parameter": "b", "value": "1", "confidence": 0.876},
                     doc_id="D", anchor="sec-1")
    assert it.to_dict()["confidence"] == 0.88
    it2 = Atom(id="x", entity="a", parameter="b", value=None, unit="", type="spec",
               condition="", source_doc="D", section="sec-1",
               evidence_ref="kb/D/main.md#sec-1", confidence=0.5, flags=("z", "a"))
    assert it2.to_dict()["flags"] == ["a", "z"]


def test_build_system_prompt_includes_both():
    p = build_system_prompt()
    assert "Atomic Extraction Rules" in p and len(p) > 200


def test_extractor_forces_anchor(tmp_path):
    from kb_extract.wiki.atoms.extractor import extract_atoms
    doc = tmp_path / "kb" / "D"
    doc.mkdir(parents=True)
    (doc / "main.md").write_text('<a id="sec-0001"></a>\n# Hinge\n\nForce 5 N.\n', encoding="utf-8")

    class LLM:
        def chat(self, m):
            return '[{"entity":"hinge","parameter":"force","value":"5","unit":"N","type":"spec"}]'

    r = extract_atoms(tmp_path, LLM())
    assert r.total_atoms == 1
    assert r.atoms_by_doc["D"][0].section == "sec-0001"
