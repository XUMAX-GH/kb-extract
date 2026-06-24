from pathlib import Path

import pytest

from kb_extract.errors import RedactionPolicyError
from kb_extract.redaction import RedactionPolicy, TextRule, load_policy


def _write_policy(root: Path, body: str) -> Path:
    p = root / "redaction.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_load_policy_absent_default_returns_none(tmp_path):
    assert load_policy(tmp_path, None) is None


def test_load_policy_explicit_missing_raises(tmp_path):
    with pytest.raises(RedactionPolicyError):
        load_policy(tmp_path, tmp_path / "nope.toml")


def test_load_policy_parses_fields(tmp_path):
    _write_policy(
        tmp_path,
        "[redaction]\n"
        "enabled = true\n"
        "[[redaction.text]]\n"
        "pattern = '(?i)\\b[MH]\\d{6,8}\\b'\n"
        'replacement = "[PN-REDACTED]"\n'
        "[redaction.logos]\n"
        'sha256 = ["abc"]\n'
        'filename_globs = ["*logo*"]\n'
        'alt_globs = ["*logo*"]\n',
    )
    policy = load_policy(tmp_path, None)
    assert isinstance(policy, RedactionPolicy)
    assert policy.enabled is True
    assert policy.text_rules == (
        TextRule(pattern=r"(?i)\b[MH]\d{6,8}\b", replacement="[PN-REDACTED]"),
    )
    assert policy.logo_sha256 == ("abc",)
    assert policy.logo_filename_globs == ("*logo*",)
    assert policy.logo_alt_globs == ("*logo*",)
    assert len(policy.policy_sha256) == 64


def test_load_policy_invalid_regex_raises(tmp_path):
    _write_policy(
        tmp_path,
        "[redaction]\nenabled = true\n[[redaction.text]]\n"
        'pattern = "("\nreplacement = "x"\n',
    )
    with pytest.raises(RedactionPolicyError):
        load_policy(tmp_path, None)


def test_load_policy_invalid_toml_raises(tmp_path):
    _write_policy(tmp_path, "this is = = not toml")
    with pytest.raises(RedactionPolicyError):
        load_policy(tmp_path, None)
