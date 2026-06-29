import json

from click.testing import CliRunner

from kb_extract.cli import main
from kb_extract.wiki.atoms.schema import coerce_atom
from kb_extract.wiki.graph.prompts import compose_messages
from kb_extract.wiki.graph.render import render_json, render_markdown
from kb_extract.wiki.graph.schema import coerce_edge, parse_edges
from kb_extract.wiki.providers.cached import prompt_hash


def _atom(entity="hinge", parameter="force", **o):
    return coerce_atom({"entity": entity, "parameter": parameter, "value": "5",
                        "unit": "N", "type": "spec", **o}, doc_id="D", anchor="sec-0001")


VALID = {"a1", "a2"}


def test_coerce_drops_unknown_relation():
    assert coerce_edge({"source_id": "a1", "target_id": "a2", "relation": "loves"},
                       doc_id="D", valid_ids=VALID) is None


def test_coerce_drops_hallucinated_and_self_edges():
    assert coerce_edge({"source_id": "a1", "target_id": "ghost", "relation": "affects"},
                       doc_id="D", valid_ids=VALID) is None
    assert coerce_edge({"source_id": "a1", "target_id": "a1", "relation": "affects"},
                       doc_id="D", valid_ids=VALID) is None


def test_missing_evidence_flags_pending_and_caps_conf():
    e = coerce_edge({"source_id": "a1", "target_id": "a2", "relation": "affects",
                     "confidence": 0.9}, doc_id="D", valid_ids=VALID)
    assert e is not None and "待验证" in e.flags and e.confidence <= 0.3


def test_render_json_reproducible():
    e1 = coerce_edge({"source_id": "a1", "target_id": "a2", "relation": "affects",
                      "evidence_ref": "x"}, doc_id="D", valid_ids=VALID)
    e2 = coerce_edge({"source_id": "a1", "target_id": "a2", "relation": "affects",
                      "evidence_ref": "x"}, doc_id="D", valid_ids=VALID)
    assert render_json([e1]) == render_json([e2])
    assert render_markdown("D", [], {}).startswith("# Graph: D")


def test_parse_edges_tolerates_fences():
    assert parse_edges('```json\n[{"source_id":"a"}]\n```') == [{"source_id": "a"}]


def test_cli_graph_cached(tmp_path):
    g = tmp_path / "kb" / "DOC1" / "graph"
    g.mkdir(parents=True)
    a1, a2 = _atom(), _atom(parameter="latency")
    g.joinpath("atoms.json").write_text(json.dumps([a1.to_dict(), a2.to_dict()]), encoding="utf-8")
    g.joinpath("modules.json").write_text(json.dumps({"Mechanical": [a1.id, a2.id]}), encoding="utf-8")
    resp = json.dumps([{"source_id": a1.id, "target_id": a2.id, "relation": "affects",
                        "evidence_ref": a1.id, "confidence": 0.8}])
    briefs = [{"id": x.id, "entity": x.entity, "parameter": x.parameter,
               "value": x.value, "type": x.type} for x in (a1, a2)]
    h = prompt_hash(compose_messages(atoms=briefs))
    rf = tmp_path / "resp.json"
    rf.write_text(json.dumps({h: resp}), encoding="utf-8")
    r = CliRunner().invoke(main, ["wiki", "graph", str(tmp_path), "--provider", "cached",
                                  "--responses-file", str(rf), "--json"])
    assert r.exit_code == 0, r.output
    assert json.loads((g / "edges.json").read_text(encoding="utf-8"))[0]["relation"] == "affects"
    assert (g / "graph.md").exists()
