from pathlib import Path

from kb_extract.wiki.orchestrator import verify_wikilinks


def _page(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_verify_wikilinks_passes_when_targets_exist(tmp_path: Path):
    wiki = tmp_path / "wiki"
    _page(wiki / "a.md", "see [[b]]")
    _page(wiki / "b.md", "hello")
    assert verify_wikilinks(wiki) == []


def test_verify_wikilinks_flags_dead_link(tmp_path: Path):
    wiki = tmp_path / "wiki"
    _page(wiki / "a.md", "see [[missing-note]]")
    violations = verify_wikilinks(wiki)
    assert any("missing-note" in v for v in violations)


def test_verify_wikilinks_resolves_pathed_and_labeled(tmp_path: Path):
    wiki = tmp_path / "wiki"
    _page(wiki / "a.md", "see [[sys/sub/_index|Label]]")
    _page(wiki / "sys" / "sub" / "_index.md", "x")
    assert verify_wikilinks(wiki) == []
