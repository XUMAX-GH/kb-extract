import ast
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from kb_extract.adapters.base import Registry
from kb_extract.contracts import AssetRef, ExtractionMeta, ExtractionResult, SectionNode
from kb_extract.errors import RedactionPolicyError
from kb_extract.orchestrator import run
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


class _RedactTestAdapter:
    name = "_redact"
    version = "0.1"
    extensions = (".rdt",)

    def extract(self, src, out_dir_tmp):
        assets_dir = out_dir_tmp / "assets"
        assets_dir.mkdir(exist_ok=True)
        (assets_dir / "logo_1.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
        sha = hashlib.sha256((assets_dir / "logo_1.png").read_bytes()).hexdigest()
        md = (
            '<!-- generated -->\n\n'
            '<a id="sec-0001"></a>\n'
            '# Doc\n\n'
            'Part M1320001 is secret.\n\n'
            '![company logo](assets/logo_1.png)\n'
        )
        root = SectionNode(
            node_id="0000", title="Root", level=0, page_start=1, page_end=1,
            anchor="", language="und",
            children=(SectionNode(
                node_id="0001", title="Doc", level=1, page_start=1, page_end=1,
                anchor="sec-0001", language="und",
            ),),
        )
        assets = (AssetRef(kind="image", rel_path="assets/logo_1.png", page=1, sha256=sha, alt="company logo"),)
        meta = ExtractionMeta(
            source_path=src.as_posix(),
            source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
            source_bytes=src.stat().st_size,
            source_mtime_iso="t",
            adapter_name=self.name,
            adapter_version=self.version,
            tool_versions={},
            extracted_at_iso="t",
            outline_source="bookmark",
            status="ok",
        )
        return ExtractionResult(markdown=md, index=root, tables=(), assets=assets, meta=meta)


def _project_with_policy(tmp_path, policy_body):
    project = tmp_path / "P"
    project.mkdir()
    (project / "doc.rdt").write_bytes(b"x")
    (project / "redaction.toml").write_text(policy_body, encoding="utf-8")
    return project


POLICY = (
    '[redaction]\nenabled = true\n'
    '[[redaction.text]]\n'
    "pattern = '(?i)\\b[MH]\\d{6,8}\\b'\n"
    'replacement = "[PN-REDACTED]"\n'
    '[redaction.logos]\nfilename_globs = ["*logo*"]\n'
)


def test_run_applies_redaction_and_writes_sidecar(tmp_path):
    project = _project_with_policy(tmp_path, POLICY)
    reg = Registry()
    reg.register(_RedactTestAdapter())
    report = run(project, registry=reg)
    assert report.ok_count == 1
    out = project / "kb" / "doc"
    main_md = (out / "main.md").read_text(encoding="utf-8")
    assert "M1320001" not in main_md
    assert "[PN-REDACTED]" in main_md
    assert "assets/logo_1.png" not in main_md
    assert '<a id="sec-0001"></a>' in main_md
    assert not (out / "assets" / "logo_1.png").exists()
    sidecar = json.loads((out / "redaction.json").read_text(encoding="utf-8"))
    assert sidecar["pn_redacted"] == 1
    assert sidecar["logos_dropped"] == 1
    assert len(sidecar["policy_sha256"]) == 64
    assert report.pn_redacted == 1
    assert report.logos_dropped == 1


def test_run_without_policy_writes_no_sidecar(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "doc.rdt").write_bytes(b"x")
    reg = Registry()
    reg.register(_RedactTestAdapter())
    run(project, registry=reg)
    out = project / "kb" / "doc"
    assert "M1320001" in (out / "main.md").read_text(encoding="utf-8")
    assert not (out / "redaction.json").exists()


def test_run_reprocesses_when_policy_is_added_after_initial_extract(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "doc.rdt").write_bytes(b"x")
    reg = Registry()
    reg.register(_RedactTestAdapter())
    run(project, registry=reg)
    (project / "redaction.toml").write_text(POLICY, encoding="utf-8")

    report = run(project, registry=reg)

    out = project / "kb" / "doc"
    assert report.ok_count == 1
    assert report.unchanged_count == 0
    assert "M1320001" not in (out / "main.md").read_text(encoding="utf-8")
    assert (out / "redaction.json").exists()


def test_run_propagates_redaction_into_zip_children(tmp_path):
    project = _project_with_policy(tmp_path, POLICY)
    (project / "doc.rdt").unlink()
    with zipfile.ZipFile(project / "bundle.zip", "w") as zf:
        zf.writestr("doc.rdt", b"x")
    reg = Registry()
    reg.register(_RedactTestAdapter())

    report = run(project, registry=reg)

    child_out = project / "kb" / "bundle" / "_unpacked" / "kb" / "doc"
    assert report.ok_count == 1
    assert "M1320001" not in (child_out / "main.md").read_text(encoding="utf-8")
    assert (child_out / "redaction.json").exists()


def test_run_refreshes_zip_redaction_when_registry_is_reused(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    with zipfile.ZipFile(project / "bundle.zip", "w") as zf:
        zf.writestr("doc.rdt", b"x")
    reg = Registry()
    reg.register(_RedactTestAdapter())
    run(project, registry=reg)
    (project / "redaction.toml").write_text(POLICY, encoding="utf-8")

    report = run(project, registry=reg)

    child_out = project / "kb" / "bundle" / "_unpacked" / "kb" / "doc"
    assert report.ok_count == 1
    assert "M1320001" not in (child_out / "main.md").read_text(encoding="utf-8")
    assert (child_out / "redaction.json").exists()


def test_run_accumulates_zip_child_redaction_counts(tmp_path):
    project = _project_with_policy(tmp_path, POLICY)
    (project / "doc.rdt").unlink()
    with zipfile.ZipFile(project / "bundle.zip", "w") as zf:
        zf.writestr("doc.rdt", b"x")
    reg = Registry()
    reg.register(_RedactTestAdapter())

    report = run(project, registry=reg)

    assert report.pn_redacted == 1
    assert report.logos_dropped == 1


def test_run_does_not_enable_zip_embedded_policy_when_parent_has_no_policy(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    with zipfile.ZipFile(project / "bundle.zip", "w") as zf:
        zf.writestr("doc.rdt", b"x")
        zf.writestr("redaction.toml", POLICY)
    reg = Registry()
    reg.register(_RedactTestAdapter())

    report = run(project, registry=reg)

    child_out = project / "kb" / "bundle" / "_unpacked" / "kb" / "doc"
    assert report.pn_redacted == 0
    assert report.logos_dropped == 0
    assert "M1320001" in (child_out / "main.md").read_text(encoding="utf-8")
    assert not (child_out / "redaction.json").exists()


_PN_RULE = TextRule(pattern=r"(?i)\b[MH]\d{6,8}\b", replacement="[PN-REDACTED]")


def _result_with_pn_in_index_and_meta():
    root = SectionNode(
        node_id="0000", title="M1320001 Root", level=0, page_start=1, page_end=1,
        anchor="", language="und",
        children=(SectionNode(
            node_id="0001", title="Leaf H1234567", level=1, page_start=1, page_end=1,
            anchor="sec-0001", language="und",
        ),),
    )
    meta = ExtractionMeta(
        source_path="M9000006.pdf", source_sha256="a" * 64, source_bytes=1,
        source_mtime_iso="t", adapter_name="p", adapter_version="v",
        tool_versions={}, extracted_at_iso="t", outline_source="bookmark",
        status="partial", warnings=("warn about M1110000",),
        skipped_reasons=("skipped H2220000 page",),
    )
    md = '<a id="sec-0001"></a>\n# Leaf\n\nBody M1320001 here.\n'
    return ExtractionResult(markdown=md, index=root, tables=(), assets=(), meta=meta)


def test_apply_redacts_index_titles_recursively():
    new_result, _, _ = apply_to_result(
        _result_with_pn_in_index_and_meta(), _policy(text_rules=(_PN_RULE,))
    )
    assert new_result.index.title == "[PN-REDACTED] Root"
    assert new_result.index.children[0].title == "Leaf [PN-REDACTED]"
    # anchors and ids are never touched
    assert new_result.index.children[0].anchor == "sec-0001"
    assert new_result.index.children[0].node_id == "0001"


def test_apply_redacts_meta_source_path_and_messages():
    new_result, _, _ = apply_to_result(
        _result_with_pn_in_index_and_meta(), _policy(text_rules=(_PN_RULE,))
    )
    assert new_result.meta.source_path == "[PN-REDACTED].pdf"
    assert new_result.meta.warnings == ("warn about [PN-REDACTED]",)
    assert new_result.meta.skipped_reasons == ("skipped [PN-REDACTED] page",)
    # non-text fields untouched
    assert new_result.meta.source_sha256 == "a" * 64


def test_apply_counts_include_markdown_index_and_meta():
    _, stats, _ = apply_to_result(
        _result_with_pn_in_index_and_meta(), _policy(text_rules=(_PN_RULE,))
    )
    # 1 in markdown + 2 in index titles + 3 in meta (source_path, warning, skipped)
    assert stats.pn_redacted == 6


def test_run_redacts_index_and_meta_json_on_disk(tmp_path):
    from dataclasses import replace as _replace

    class _PNInIndexMetaAdapter(_RedactTestAdapter):
        def extract(self, src, out_dir_tmp):
            result = super().extract(src, out_dir_tmp)
            index = _replace(result.index, title="M1320001 Root")
            meta = _replace(result.meta, source_path="M1320001.rdt")
            return _replace(result, index=index, meta=meta)

    project = _project_with_policy(tmp_path, POLICY)
    reg = Registry()
    reg.register(_PNInIndexMetaAdapter())
    run(project, registry=reg)
    out = project / "kb" / "doc"
    index_raw = (out / "index.json").read_text(encoding="utf-8")
    meta_raw = (out / "meta.json").read_text(encoding="utf-8")
    assert "M1320001" not in index_raw
    assert "M1320001" not in meta_raw
    assert "[PN-REDACTED]" in index_raw
    assert "[PN-REDACTED]" in meta_raw


def test_redaction_is_deterministic_across_two_runs(tmp_path):
    reg1, reg2 = Registry(), Registry()
    reg1.register(_RedactTestAdapter())
    reg2.register(_RedactTestAdapter())

    def build(root):
        root.mkdir(parents=True)
        (root / "doc.rdt").write_bytes(b"x")
        (root / "redaction.toml").write_text(POLICY, encoding="utf-8")
        return root

    r1 = build(tmp_path / "a")
    r2 = build(tmp_path / "b")
    run(r1, registry=reg1)
    run(r2, registry=reg2)
    md1 = (r1 / "kb" / "doc" / "main.md").read_bytes()
    md2 = (r2 / "kb" / "doc" / "main.md").read_bytes()
    assert md1 == md2
    side1 = (r1 / "kb" / "doc" / "redaction.json").read_bytes()
    side2 = (r2 / "kb" / "doc" / "redaction.json").read_bytes()
    assert side1 == side2
    assert b"\r" not in md1  # LF only


def test_redaction_module_imports_no_llm_sdk():
    import kb_extract.redaction as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                names.add(n.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    forbidden = {"openai", "anthropic", "litellm", "langchain", "transformers"}
    assert not (names & forbidden)
