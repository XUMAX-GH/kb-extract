from kb_extract.wiki.requirements.models import TestItem, coerce_item, find_verbatim


def test_find_verbatim_exact_substring_returns_original():
    body = "The torque shall be 5 Nm.\nMeasured per spec."
    assert find_verbatim("The torque shall be 5 Nm.", body) == "The torque shall be 5 Nm."


def test_find_verbatim_normalizes_whitespace_but_returns_original_span():
    body = "Stiffness   >=  5\n  N/mm across the hinge."
    got = find_verbatim("Stiffness >= 5 N/mm", body)
    assert got == "Stiffness   >=  5\n  N/mm"


def test_find_verbatim_not_present_returns_none():
    body = "The torque shall be 5 Nm."
    assert find_verbatim("The mass shall be 200 g.", body) is None


def test_find_verbatim_empty_quote_returns_none():
    assert find_verbatim("", "anything") is None
    assert find_verbatim("   ", "anything") is None


def test_coerce_item_keeps_verifiable_quote():
    body = "The hinge torque shall be 5 Nm at room temperature."
    obj = {
        "Function": "Torque",
        "What": "Hinge torque 5 Nm",
        "EvidenceQuote": "The hinge torque shall be 5 Nm",
    }
    item = coerce_item(obj, anchor="sec-0003", section_title="3.2",
                       category="Mechanical", section_body=body)
    assert item.evidence_quote == "The hinge torque shall be 5 Nm"


def test_coerce_item_drops_unverifiable_quote():
    body = "The hinge torque shall be 5 Nm."
    obj = {"What": "X", "EvidenceQuote": "totally invented sentence"}
    item = coerce_item(obj, anchor="sec-0003", section_title="3.2",
                       category="Mechanical", section_body=body)
    assert item.evidence_quote == ""


def test_coerce_item_missing_quote_is_empty():
    item = coerce_item({"What": "X"}, anchor="sec-0003", section_title="3.2",
                       category="Mechanical", section_body="body")
    assert item.evidence_quote == ""


def test_to_dict_includes_evidence_quote():
    it = TestItem(category="C", function="F", what="W", how="H",
                  sample_size="S", source_document="D", source_section="3.2",
                  evidence_ref="sec-0001", evidence_quote="Q")
    assert it.to_dict()["EvidenceQuote"] == "Q"
