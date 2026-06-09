
import pytest

from kb_extract.layout import find_project_root, target_dir


def test_target_dir_strips_extension(tmp_path):
    project = tmp_path / "BUR-K"
    project.mkdir()
    src = project / "M1324399-DOC_MP44_MAIN-REV_E.pdf"
    src.write_bytes(b"%PDF-1.7")
    out = target_dir(project, src)
    assert out == project / "kb" / "M1324399-DOC_MP44_MAIN-REV_E"


def test_target_dir_handles_double_extension(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    src = project / "archive.tar.gz"
    src.write_bytes(b"x")
    out = target_dir(project, src)
    # Only the final .gz is stripped (we treat .tar as part of stem).
    assert out == project / "kb" / "archive.tar"


def test_target_dir_for_nested_source_preserves_subdir(tmp_path):
    project = tmp_path / "P"
    (project / "subdir").mkdir(parents=True)
    src = project / "subdir" / "doc.pdf"
    src.write_bytes(b"x")
    out = target_dir(project, src)
    assert out == project / "kb" / "subdir" / "doc"


def test_find_project_root_returns_self_for_directory_input(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    assert find_project_root(project) == project


def test_find_project_root_for_file_returns_immediate_parent_if_no_kb_ancestor(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    src = project / "doc.pdf"
    src.write_bytes(b"x")
    assert find_project_root(src) == project


def test_find_project_root_walks_up_to_kb_marker(tmp_path):
    project = tmp_path / "P"
    (project / "kb").mkdir(parents=True)
    (project / "sub" / "deep").mkdir(parents=True)
    src = project / "sub" / "deep" / "doc.pdf"
    src.write_bytes(b"x")
    assert find_project_root(src) == project


def test_target_dir_rejects_source_outside_project(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    outside = tmp_path / "other.pdf"
    outside.write_bytes(b"x")
    with pytest.raises(ValueError):
        target_dir(project, outside)
