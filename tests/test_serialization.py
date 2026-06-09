from kb_extract.contracts import SectionNode
from kb_extract.serialization import (
    canonical_index_bytes,
    serialize_index_json,
    serialize_markdown,
    serialize_meta_json,
)


def _sn(**kw) -> SectionNode:
    defaults: dict = dict(
        node_id="0001", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="und", children=(),
    )
    defaults.update(kw)
    return SectionNode(**defaults)


def test_serialize_index_json_has_trailing_newline_and_indent2():
    out = serialize_index_json(_sn())
    assert out.endswith("\n")
    assert "\n  " in out  # indent=2 produces 2-space leading whitespace
    assert "\u4e2d" not in out or "中" in out  # ensure_ascii=False keeps unicode literal


def test_serialize_index_json_keeps_chinese_unescaped():
    out = serialize_index_json(_sn(title="第一章"))
    assert "第一章" in out
    assert "\\u" not in out


def test_serialize_index_json_keys_sorted():
    out = serialize_index_json(_sn(title="x"))
    # Keys appear in alphabetical order
    keys_in_order = [line.strip().split('"')[1] for line in out.splitlines() if line.strip().startswith('"')]
    assert keys_in_order == sorted(keys_in_order)


def test_serialize_index_json_includes_children_recursively():
    leaf = _sn(node_id="0001.0001", title="Leaf", level=1, anchor="sec-0001-0001")
    parent = _sn(children=(leaf,))
    out = serialize_index_json(parent)
    assert "Leaf" in out
    assert "sec-0001-0001" in out


def test_canonical_index_bytes_is_bytes_of_serialize_index_json():
    n = _sn(title="hi")
    assert canonical_index_bytes(n) == serialize_index_json(n).encode("utf-8")


def test_serialize_markdown_ends_with_single_trailing_newline():
    assert serialize_markdown("hello") == "hello\n"
    assert serialize_markdown("hello\n") == "hello\n"
    assert serialize_markdown("hello\n\n\n") == "hello\n"


def test_serialize_markdown_normalizes_crlf_to_lf():
    assert serialize_markdown("a\r\nb\r\n") == "a\nb\n"


def test_serialize_markdown_no_bom():
    assert not serialize_markdown("x").startswith("\ufeff")


def test_serialize_meta_json_includes_all_fields_sorted_and_trailing_newline():
    from kb_extract.contracts import ExtractionMeta
    m = ExtractionMeta(
        source_path="x.pdf", source_sha256="a" * 64, source_bytes=1, source_mtime_iso="t",
        adapter_name="p", adapter_version="v", tool_versions={"b": "2", "a": "1"},
        extracted_at_iso="t", outline_source="bookmark", status="ok",
    )
    out = serialize_meta_json(m)
    assert out.endswith("\n")
    # tool_versions inner dict keys also sorted
    a_idx = out.index('"a": "1"')
    b_idx = out.index('"b": "2"')
    assert a_idx < b_idx
