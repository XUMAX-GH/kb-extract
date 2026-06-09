from kb_extract.discovery import discover_sources


def test_discover_returns_files_only_sorted(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "b.docx").write_bytes(b"b")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.xlsx").write_bytes(b"c")
    out = discover_sources(tmp_path)
    rels = [p.relative_to(tmp_path).as_posix() for p in out]
    assert rels == sorted(rels)
    assert rels == ["a.pdf", "b.docx", "sub/c.xlsx"]


def test_discover_skips_kb_directory(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "kb").mkdir()
    (tmp_path / "kb" / "manifest.sqlite").write_bytes(b"x")
    (tmp_path / "kb" / "a" / "main.md").parent.mkdir(parents=True)
    (tmp_path / "kb" / "a" / "main.md").write_bytes(b"y")
    rels = [p.relative_to(tmp_path).as_posix() for p in discover_sources(tmp_path)]
    assert rels == ["a.pdf"]


def test_discover_skips_dot_git(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_bytes(b"ref: refs/heads/main")
    rels = [p.relative_to(tmp_path).as_posix() for p in discover_sources(tmp_path)]
    assert rels == ["a.pdf"]


def test_discover_skips_tmp_dirs(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "out.tmp").mkdir()
    (tmp_path / "out.tmp" / "x.txt").write_bytes(b"y")
    rels = [p.relative_to(tmp_path).as_posix() for p in discover_sources(tmp_path)]
    assert rels == ["a.pdf"]


def test_discover_respects_gitignore_at_root(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "secret.pdf").write_bytes(b"s")
    (tmp_path / ".gitignore").write_text("secret.pdf\n", encoding="utf-8")
    rels = [p.relative_to(tmp_path).as_posix() for p in discover_sources(tmp_path)]
    assert "secret.pdf" not in rels
    assert "a.pdf" in rels


def test_discover_single_file_input_returns_itself_if_supported(tmp_path):
    src = tmp_path / "a.pdf"
    src.write_bytes(b"a")
    out = discover_sources(src)
    assert out == [src.resolve()]
