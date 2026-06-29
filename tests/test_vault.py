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
    assert ent.exists()
    txt = ent.read_text(encoding="utf-8")
    assert "[[force]]" in txt and "../../RawMD/DOC1.md#" in txt
    assert cmp.exists() and "[冲突]" in cmp.read_text(encoding="utf-8")


def test_wiki_skip_existing_preserves_pages(tmp_path):
    _seed(tmp_path, "DOC1", [_atom(doc="DOC1")])
    ent = tmp_path / "vault" / "Wiki" / "entities" / "hinge.md"
    ent.parent.mkdir(parents=True, exist_ok=True)
    ent.write_bytes(b"PRESERVED")
    r = CliRunner().invoke(
        main, ["vault", "wiki", str(tmp_path), "--provider", "mock",
               "--skip-existing", "--json"])
    assert r.exit_code == 0, r.output
    assert ent.read_bytes() == b"PRESERVED"


def test_build_rewrites_graph_links(tmp_path):
    g = _seed(tmp_path, "DOC1", [_atom()])
    g.joinpath("graph.md").write_text("- x (main.md#sec-0001)\n", encoding="utf-8")
    r = CliRunner().invoke(main, ["vault", "build", str(tmp_path), "--json"])
    assert r.exit_code == 0, r.output
    gm = (tmp_path / "vault" / "Graph" / "DOC1" / "graph.md").read_text(encoding="utf-8")
    assert "../../RawMD/DOC1.md#sec-0001" in gm
