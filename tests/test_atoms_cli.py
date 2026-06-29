import json

from click.testing import CliRunner

from kb_extract.cli import main


def _proj(tmp_path):
    d = tmp_path / "kb" / "DOC1"
    d.mkdir(parents=True)
    (d / "main.md").write_text('<a id="sec-0001"></a>\n# Hinge\n\nForce 5 N.\n', encoding="utf-8")
    return tmp_path


def test_atoms_mock_runs(tmp_path):
    r = CliRunner().invoke(main, ["wiki", "atoms", str(_proj(tmp_path))])
    assert r.exit_code == 0 and "wiki atoms:" in r.output


def test_atoms_cached(tmp_path):
    proj = _proj(tmp_path)
    from kb_extract.wiki.atoms.prompts import compose_messages
    from kb_extract.wiki.providers.cached import prompt_hash
    from kb_extract.wiki.requirements.sections import chunk_body, iter_content_sections

    sec = iter_content_sections(proj / "kb", "DOC1")[0]
    chunk = chunk_body(sec.body, max_chars=6000)[0]
    h = prompt_hash(compose_messages(anchor=sec.anchor, section_title=sec.title, section_body=chunk))
    rf = tmp_path / "r.json"
    rf.write_text(json.dumps(
        {h: '[{"entity":"hinge","parameter":"force","value":"5","unit":"N","type":"spec"}]'}
    ), encoding="utf-8")
    r = CliRunner().invoke(main, [
        "wiki", "atoms", str(proj), "--provider", "cached", "--responses-file", str(rf), "--json",
    ])
    assert r.exit_code == 0, r.output
    out = json.loads((proj / "kb" / "DOC1" / "graph" / "atoms.json").read_text(encoding="utf-8"))
    assert out[0]["evidence_ref"] == "kb/DOC1/main.md#sec-0001"
