import json
from pathlib import Path

from click.testing import CliRunner

from kb_extract.cli import main


def _make_project(tmp_path: Path) -> Path:
    doc = tmp_path / "kb" / "DOC1"
    doc.mkdir(parents=True)
    (doc / "main.md").write_text(
        '<a id="sec-0001"></a>\n# 3.2 Hinge\n\nStiffness >= 5 N/mm.\n',
        encoding="utf-8",
    )
    (doc / "index.json").write_text(
        json.dumps({"title": "r", "anchor": "", "children": [
            {"title": "3.2 Hinge", "anchor": "sec-0001", "children": []}]}),
        encoding="utf-8",
    )
    return tmp_path


def test_requirements_mock_runs(tmp_path):
    proj = _make_project(tmp_path)
    res = CliRunner().invoke(main, ["wiki", "requirements", str(proj)])
    assert res.exit_code == 0, res.output
    assert "wiki requirements:" in res.output


def test_requirements_cached_uses_responses(tmp_path):
    proj = _make_project(tmp_path)
    from kb_extract.wiki.providers.cached import prompt_hash
    from kb_extract.wiki.requirements.prompts import compose_messages
    from kb_extract.wiki.requirements.router import route_heading
    from kb_extract.wiki.sections import read_section_body

    body = read_section_body(proj / "kb", "DOC1", "sec-0001")
    domain = route_heading("3.2 Hinge").domain
    msgs = compose_messages(domain=domain, anchor="sec-0001",
                            section_title="3.2 Hinge", section_body=body)
    responses = {prompt_hash(msgs): '[{"Category":"Mechanical","What":"Stiffness >= 5"}]'}
    rf = tmp_path / "responses.json"
    rf.write_text(json.dumps(responses), encoding="utf-8")

    res = CliRunner().invoke(main, [
        "wiki", "requirements", str(proj),
        "--provider", "cached", "--responses-file", str(rf), "--json",
    ])
    assert res.exit_code == 0, res.output
    summary = json.loads(res.output.strip().splitlines()[-1])
    assert summary["items"] == 1
    out = json.loads((proj / "kb" / "DOC1" / "requirements.json").read_text())
    assert out[0]["EvidenceRef"] == "sec-0001"


def test_github_models_without_token_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_MODELS_TOKEN", raising=False)
    proj = _make_project(tmp_path)
    res = CliRunner().invoke(main, [
        "wiki", "requirements", str(proj), "--provider", "github-models",
    ])
    assert res.exit_code != 0
