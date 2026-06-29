import json

from click.testing import CliRunner

from kb_extract.cli import main
from kb_extract.vault.builder import agents_md, render_index
from kb_extract.wiki.atoms.schema import coerce_atom


def _atom(entity="hinge", parameter="force", doc="D", sec="sec-0001"):
    a = coerce_atom({"entity": entity, "parameter": parameter, "value": "5",
                     "unit": "N", "type": "spec"}, doc_id=doc, anchor=sec)
    return a


def _seed(tmp_path, doc, atoms):
    g = tmp_path / "kb" / doc / "graph"
    g.mkdir(parents=True)
    (g.parent / "main.md").write_text(f"# {doc}\n\nbody\n", encoding="utf-8")
    g.joinpath("atoms.json").write_text(json.dumps([a.to_dict() for a in atoms]), encoding="utf-8")
    return g


def test_agents_md_has_schema():
    t = agents_md()
    assert "[[" in t and "[待验证]" in t and "Raw" in t


def test_index_reproducible():
    assert render_index(["b", "a"]) == render_index(["a", "b"])


def test_build_assembles_vault(tmp_path):
    _seed(tmp_path, "DOC1", [_atom()])
    r = CliRunner().invoke(main, ["vault", "build", str(tmp_path), "--json"])
    assert r.exit_code == 0, r.output
    v = tmp_path / "vault"
    assert (v / "AGENTS.md").exists() and (v / "index.md").exists()
    assert (v / "RawMD" / "DOC1.md").exists()
    assert (v / "Graph" / "DOC1" / "atoms.json").exists()


def test_wiki_entity_and_compare(tmp_path):
    _seed(tmp_path, "DOC1", [_atom(doc="DOC1")])
    _seed(tmp_path, "DOC2", [_atom(doc="DOC2")])
    r = CliRunner().invoke(main, ["vault", "wiki", str(tmp_path), "--provider", "mock", "--json"])
    assert r.exit_code == 0, r.output
    ent = tmp_path / "vault" / "Wiki" / "entities" / "hinge.md"
    cmp = tmp_path / "vault" / "Wiki" / "compare" / "hinge.md"
    assert ent.exists() and "[[force]]" in ent.read_text(encoding="utf-8")
    assert cmp.exists() and "[冲突]" in cmp.read_text(encoding="utf-8")
