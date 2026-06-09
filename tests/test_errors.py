import pytest

from kb_extract.errors import AdapterError, HardnessViolation


def test_hardness_violation_carries_invariant_id_and_detail():
    err = HardnessViolation(invariant="H3", detail="anchor 'sec-0001' appears 2 times")
    assert err.invariant == "H3"
    assert err.detail == "anchor 'sec-0001' appears 2 times"
    assert "H3" in str(err)
    assert "anchor 'sec-0001'" in str(err)


def test_hardness_violation_is_an_exception():
    with pytest.raises(HardnessViolation) as excinfo:
        raise HardnessViolation(invariant="H5", detail="asset orphan: assets/foo.png")
    assert excinfo.value.invariant == "H5"


def test_adapter_error_is_an_exception():
    with pytest.raises(AdapterError):
        raise AdapterError("pdf parse failed at page 17")


def test_hardness_violation_is_not_adapter_error():
    # Orchestrator catches AdapterError for skip-and-continue;
    # HardnessViolation must propagate (different bucket).
    assert not issubclass(HardnessViolation, AdapterError)
