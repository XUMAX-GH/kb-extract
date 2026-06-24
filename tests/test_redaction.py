from pathlib import Path

import pytest

from kb_extract.contracts import AssetRef, ExtractionMeta, ExtractionResult, SectionNode
from kb_extract.errors import RedactionPolicyError
from kb_extract.redaction import (
    RedactionPolicy,
    RedactionStats,
    TextRule,
    apply_to_result,
    load_policy,
)
from kb_extract.serialization import serialize_redaction_json


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


def _meta() -> ExtractionMeta:
    return ExtractionMeta(
        source_path="x.pdf", source_sha256="a" * 64, source_bytes=1,
        source_mtime_iso="t", adapter_name="p", adapter_version="v",
        tool_versions={}, extracted_at_iso="t", outline_source="bookmark",
        status="ok",
    )


def _result(markdown: str, assets=()) -> ExtractionResult:
    root = SectionNode(
        node_id="0000", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="und",
        children=(SectionNode(
            node_id="0001", title="Leaf", level=1, page_start=1, page_end=1,
            anchor="sec-0001", language="und",
        ),),
    )
    return ExtractionResult(markdown=markdown, index=root, tables=(), assets=assets, meta=_meta())


def _policy(text_rules=(), logo_sha256=(), filename_globs=(), alt_globs=()):
    from kb_extract.redaction import RedactionPolicy
    return RedactionPolicy(
        enabled=True, text_rules=tuple(text_rules), logo_sha256=tuple(logo_sha256),
        logo_filename_globs=tuple(filename_globs), logo_alt_globs=tuple(alt_globs),
        policy_sha256="d" * 64,
    )


def test_apply_redacts_part_numbers_and_counts():
    md = (
        '<a id="sec-0001"></a>\n'
        '# Leaf\n\n'
        'Part M1320001 and H1234567 are confidential. M9999999 too.\n'
    )
    rule = TextRule(pattern=r'(?i)\b[MH]\d{6,8}\b', replacement="[PN-REDACTED]")
    new_result, stats, dropped = apply_to_result(_result(md), _policy(text_rules=(rule,)))
    assert "M1320001" not in new_result.markdown
    assert "H1234567" not in new_result.markdown
    assert new_result.markdown.count("[PN-REDACTED]") == 3
    assert stats == RedactionStats(pn_redacted=3, logos_dropped=0)
    assert dropped == ()


def test_apply_preserves_anchor_line():
    md = '<a id="sec-0001"></a>\n# Leaf\n\nM1320001\n'
    rule = TextRule(pattern=r'(?i)\b[MH]\d{6,8}\b', replacement="[PN-REDACTED]")
    new_result, _, _ = apply_to_result(_result(md), _policy(text_rules=(rule,)))
    assert '<a id="sec-0001"></a>' in new_result.markdown


def _logo_md() -> str:
    return (
        '<a id="sec-0001"></a>\n'
        '# Leaf\n\n'
        '![company logo](assets/logo_1.png)\n\n'
        '![figure](assets/fig_2.png)\n'
    )


def test_apply_drops_logo_by_sha256():
    assets = (
        AssetRef(kind="image", rel_path="assets/logo_1.png", page=1, sha256="L" * 64, alt="company logo"),
        AssetRef(kind="image", rel_path="assets/fig_2.png", page=1, sha256="F" * 64, alt="figure"),
    )
    new_result, stats, dropped = apply_to_result(
        _result(_logo_md(), assets), _policy(logo_sha256=("L" * 64,))
    )
    assert dropped == ("assets/logo_1.png",)
    assert "assets/logo_1.png" not in new_result.markdown
    assert "assets/fig_2.png" in new_result.markdown
    assert tuple(a.rel_path for a in new_result.assets) == ("assets/fig_2.png",)
    assert stats.logos_dropped == 1


def test_apply_drops_logo_by_filename_glob():
    assets = (AssetRef(kind="image", rel_path="assets/logo_1.png", page=1, sha256="L" * 64, alt=""),)
    _, stats, dropped = apply_to_result(_result(_logo_md(), assets), _policy(filename_globs=("*logo*",)))
    assert dropped == ("assets/logo_1.png",)
    assert stats.logos_dropped == 1


def test_apply_drops_logo_by_alt_glob():
    assets = (AssetRef(kind="image", rel_path="assets/x.png", page=1, sha256="L" * 64, alt="company logo"),)
    md = '<a id="sec-0001"></a>\n# Leaf\n\n![company logo](assets/x.png)\n'
    _, stats, dropped = apply_to_result(_result(md, assets), _policy(alt_globs=("*logo*",)))
    assert dropped == ("assets/x.png",)
    assert stats.logos_dropped == 1


def test_serialize_redaction_json_counts_only_sorted_keys():
    out = serialize_redaction_json(pn_redacted=12, logos_dropped=3, policy_sha256="e" * 64)
    assert out.endswith("\n")
    assert '"logos_dropped": 3' in out
    assert '"pn_redacted": 12' in out
    assert '"policy_sha256": "' + "e" * 64 + '"' in out
    # keys sorted: logos_dropped < pn_redacted < policy_sha256
    assert out.index("logos_dropped") < out.index("pn_redacted") < out.index("policy_sha256")
    # only the three known keys exist (no leaked source values)
    import json as _json
    assert set(_json.loads(out).keys()) == {"logos_dropped", "pn_redacted", "policy_sha256"}
