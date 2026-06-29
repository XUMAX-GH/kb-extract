import json

from click.testing import CliRunner

from kb_extract.cli import main
from kb_extract.wiki.atoms.schema import coerce_atom
from kb_extract.wiki.modules.classifier import classify
from kb_extract.wiki.modules.render import render_modules_json
from kb_extract.wiki.modules.rules import load_rules


def _atom(entity="hinge", parameter="force", **o):
    return coerce_atom({"entity": entity, "parameter": parameter, "value": "5",
                        "unit": "N", "type": "spec", **o}, doc_id="D", anchor="sec-0001")


def test_rules_have_eight_modules():
    assert len(load_rules().modules) == 8


def test_category_match_wins():
    m, pending = classify(_atom(), "3 Mechanical & Industrial Design")
    assert m == "Mechanical" and pending is False


def test_keyword_fallback_when_no_category():
    m, pending = classify(_atom(entity="battery", parameter="power"), "Unknown Chapter")
    assert m == "Electrical" and pending is False


def test_unmatched_goes_subsystems_pending():
    m, pending = classify(_atom(entity="widget", parameter="sparkle"), "Mystery")
    assert m == "Subsystems" and pending is True


def test_modules_json_reproducible_and_pending_key():
    j = render_modules_json({"Mechanical": ["b", "a"]}, ["z"])
    assert j == render_modules_json({"Mechanical": ["a", "b"]}, ["z"])
    assert json.loads(j)["_pending"] == ["z"]


def test_cli_assigns_every_atom(tmp_path):
    g = tmp_path / "kb" / "DOC1" / "graph"
    g.mkdir(parents=True)
    (g.parent / "main.md").write_text('<a id="sec-0001"></a>\n# Mechanical\n\nx\n', encoding="utf-8")
    (g / "atoms.json").write_text(json.dumps([_atom().to_dict()]), encoding="utf-8")
    r = CliRunner().invoke(main, ["wiki", "modules", str(tmp_path), "--json"])
    assert r.exit_code == 0, r.output
    mj = json.loads((g / "modules.json").read_text(encoding="utf-8"))
    assert sum(len(v) for k, v in mj.items() if k != "_pending") == 1
    assert (g / "modules" / "Mechanical.md").exists()
