import json
from pathlib import Path

from kb_extract.wiki.requirements.extractor import extract_requirements
from kb_extract.wiki.requirements.models import coerce_item, parse_items


class _StubLlm:
    name = "stub"

    def __init__(self, response):
        self._response = response

    def chat(self, messages):
        return self._response


def _make_kb(tmp_path: Path) -> Path:
    doc = tmp_path / "kb" / "DOC1"
    doc.mkdir(parents=True)
    (doc / "main.md").write_text(
        '<a id="sec-0001"></a>\n# 3.2 Hinge Stiffness\n\n'
        "Stiffness must be >= 5 N/mm.\n",
        encoding="utf-8",
    )
    index = {
        "title": "root",
        "anchor": "",
        "children": [
            {"title": "3.2 Hinge Stiffness", "anchor": "sec-0001", "children": []}
        ],
    }
    (doc / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return tmp_path


def test_parse_items_strips_fences():
    items = parse_items('```json\n[{"What": "x"}]\n```')
    assert items == [{"What": "x"}]


def test_coerce_forces_anchor():
    it = coerce_item({"What": "x", "EvidenceRef": "WRONG"},
                     anchor="sec-0009", section_title="T")
    assert it.evidence_ref == "sec-0009"
    assert it.source_section == "T"
    assert it.how == "Not explicitly defined"


def test_extract_happy_path(tmp_path):
    root = _make_kb(tmp_path)
    llm = _StubLlm('[{"Category": "Mechanical", "What": "Stiffness >= 5 N/mm"}]')
    res = extract_requirements(root, llm)
    assert res.docs == 1
    items = res.items_by_doc["DOC1"]
    assert len(items) == 1
    assert items[0].evidence_ref == "sec-0001"
    assert res.failed_sections == 0


def test_extract_isolates_bad_json(tmp_path):
    root = _make_kb(tmp_path)
    llm = _StubLlm("not json at all")
    res = extract_requirements(root, llm)
    assert res.failed_sections == 1
    assert res.total_items == 0


def test_dry_run_skips_parse(tmp_path):
    root = _make_kb(tmp_path)
    llm = _StubLlm("garbage")
    res = extract_requirements(root, llm, dry_run=True)
    assert res.ok_sections == 1
    assert res.total_items == 0
