from kb_extract.wiki.requirements.models import find_verbatim


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
